#!/usr/bin/python3
# -*- coding: utf-8 -*-

import json
import hashlib
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    backref,
    relation,
)
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    event,
    MetaData,
)
import sqlalchemy
import argparse
import telegram_send
import requests
import sys
from pprint import pprint
from datetime import datetime
import orm_sqlite
import re
from datetime import datetime

PROGRAM_START_DATE = datetime.now()
API_URL = 'https://justjoin.it/api/offers'
URL_PREFIX = 'https://justjoin.it/offers/'
VERBOSE = True
Base = declarative_base()


def check_if_offer_matches(offer, args):
    matches = {
        'category': False,
        'fully_remote': False,
        'location': False,
        'remuneration': False,
    }

    for desired_category in args.category:
        if offer.category == desired_category:
            matches['category'] = True
            break

    if args.fully_remote:
        matches['fully_remote'] = \
            offer.workplace_remote and \
            offer.interview_remote
    else:
        matches['fully_remote'] = True

    matches_location = {
        'country': False,
        'city': False
    }

    if args.location_country:
        for desired_country in args.location_country:
            if offer.country_code == desired_country:
                matches_location['country'] = True
                break
    else:
        matches_location['country'] = True

    if args.location_city:
        for desired_city in args.location_city:
            if offer.city == desired_city:
                matches_location['city'] = True
                break
    else:
        matches_location['city'] = True

    matches['location'] = \
        matches_location['country'] and \
        matches_location['city']

    matches_remuneration = {
        'contract_type': False,
        'currency': False,
        'amount': False
    }

    matches_remuneration['contract_type'] = \
        args.contract_type == offer.contract_type

    matches_remuneration['currency'] = \
        args.currency == offer.currency

    matches_remuneration['amount'] = \
        args.salary <= offer.salary_max

    matches['remuneration'] = \
        matches_remuneration['contract_type'] and \
        matches_remuneration['currency'] and \
        matches_remuneration['amount']

    return \
        matches['category'] and \
        matches['fully_remote'] and \
        matches['location'] and \
        matches['remuneration']


def send_offer(offer, dont_send):
    msg = offer.company_name+' - '+offer.title+\
        ' '+URL_PREFIX+offer.slug
    print(msg)
    if not dont_send:
        telegram_send.send(messages=[msg], parse_mode='markdown')


class Offer(Base):
    __tablename__ = 'offers'

    last_updated = Column(DateTime)
    sent = Column(Boolean)

    parent = Column(String)
    slug = Column(String, primary_key=True)
    title = Column(String)
    company_name = Column(String)

    category = Column(String)

    workplace_remote = Column(Boolean)
    interview_remote = Column(Boolean)

    country_code = Column(String(2))
    city = Column(String)

    contract_type = Column(String, primary_key=True)
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    currency = Column(String(3))

    multiloc_checksum = Column(String)

def parse_multioffer_from_api(incoming_offer_raw, db):
    undisclosed_salary = not incoming_offer_raw['employment_types']
    if undisclosed_salary:
        return
    incoming_offer_is_multiloc_parent = \
        incoming_offer_raw['multilocation'] and \
        len(incoming_offer_raw['multilocation']) > 1
    if not incoming_offer_is_multiloc_parent:
        return

    for incomming_offer_empl_option in incoming_offer_raw['employment_types']:
        if not incomming_offer_empl_option['salary']:
            return

        for multiloc_entry in incoming_offer_raw['multilocation']:
            multiloc_child_slug = multiloc_entry['slug']
            multiloc_child_offers = db.query(Offer).filter(
                Offer.slug == multiloc_child_slug,
                Offer.parent == None
            )
            for multiloc_child_offer in multiloc_child_offers:
                multiloc_child_offer.last_updated = PROGRAM_START_DATE
                multiloc_child_offer.parent = incoming_offer_raw['id']


def hash_multiloc(multiloc):
    multiloc_slugs = []
    for multiloc_entry in multiloc:
        multiloc_slugs.append(multiloc_entry['slug'])
    multiloc_slugs.sort()
    return hashlib.md5(json.dumps(multiloc_slugs).encode('utf-8')).hexdigest()


def incoming_offer_from_raw(incoming_offer_raw, incomming_offer_empl_option):
    incoming_offer = Offer()
    incoming_offer.last_updated = PROGRAM_START_DATE
    incoming_offer.slug = incoming_offer_raw['id']
    incoming_offer.contract_type = incomming_offer_empl_option['type']
    incoming_offer.title = incoming_offer_raw['title']
    incoming_offer.company_name = incoming_offer_raw['company_name']
    incoming_offer.category = incoming_offer_raw['marker_icon']
    incoming_offer.workplace_remote = \
        incoming_offer_raw['workplace_type'] == 'remote'
    incoming_offer.interview_remote = incoming_offer_raw['remote_interview']
    incoming_offer.country_code = incoming_offer_raw['country_code']
    incoming_offer.city = incoming_offer_raw['city']
    incoming_offer.salary_min = incomming_offer_empl_option['salary']['from']
    incoming_offer.salary_max = incomming_offer_empl_option['salary']['to']
    incoming_offer.currency = \
        incomming_offer_empl_option['salary']['currency']
    incoming_offer.multiloc_checksum = hash_multiloc(
        incoming_offer_raw['multilocation'])
    return incoming_offer


def add_incoming_offer(incoming_offer, db):
    db.add(incoming_offer)


def delete_offer(offer, db):
    db.delete(offer)


def offers_differ(a, b):
    return \
        a.multiloc_checksum != b.multiloc_checksum or \
        a.title != b.title or \
        a.category != b.category or \
        a.workplace_remote != b.workplace_remote or \
        a.interview_remote != b.interview_remote or \
        a.salary_min != b.salary_min or \
        a.salary_max != b.salary_max or \
        a.currency != b.currency


def parse_offer_from_api(incoming_offer_raw, db):
    undisclosed_salary = not incoming_offer_raw['employment_types']
    if undisclosed_salary:
        return

    for incomming_offer_empl_option in incoming_offer_raw['employment_types']:
        if not incomming_offer_empl_option['salary']:
            return

        incoming_offer = incoming_offer_from_raw(
            incoming_offer_raw, incomming_offer_empl_option)

        known_offers_matching_ids = db.query(Offer).filter(
            Offer.slug == incoming_offer.slug,
            Offer.contract_type == incoming_offer.contract_type,
        )

        offer_already_known = known_offers_matching_ids.count() == 1

        known_offer_matching_ids_changed = False
        if offer_already_known:
            known_offer_matching_id = known_offers_matching_ids[0]
            known_offer_matching_ids_changed = offers_differ(
                incoming_offer, known_offer_matching_id)

        if known_offer_matching_ids_changed:
            print("<-- changed: "+incoming_offer_raw['id'])
            delete_offer(known_offers_matching_ids[0], db)

        if not offer_already_known:
            add_incoming_offer(incoming_offer, db)


def check_if_offer_sent(offer):
    return offer.sent


def mark_offer_as_sent(offer):
    offer.sent = True


def get_all_known_offers(db, args):
    if not args.location_city or args.fully_remote:
        return db.query(Offer).filter(Offer.parent == None)
    else:
        return db.query(Offer)


def main():
    parser = argparse.ArgumentParser(
        description='jjit.py -- check for newest justjoin.it job offers' +
        ' and push them by telegram_send')

    parser.add_argument(
        '--category', nargs='+', required=True,
        help='categories (like devops, java, c)')
    parser.add_argument(
        '--fully_remote', action='store_true',
        help='fully remote offer (i.e. remote interview + remote workplace')
    parser.add_argument(
        '--location-country', nargs='+',
        help='locations - countries; format - ISO 3166-1 alfa-2 (e.g. PL)')
    parser.add_argument(
        '--location-city', nargs='+',
        help='locations - cities')
    parser.add_argument(
        '--salary', nargs='?', type=int, default=10000,
        help='minimum salary (assumed gross/month); default - 10000')
    parser.add_argument(
        '--currency', nargs='?', default='pln',
        help='currency (as in offer) [pln, usd, eur, gbp, chf]; default - pln')
    parser.add_argument(
        '--contract-type', nargs='?', default='ANY',
        help='contract type [permanent, b2b, mandate_contract, ANY]; ' +
        'default - ANY')
    parser.add_argument(
        '--database', default='sqlite:///jjit.sqlite3',
        help='state database; default - sqlite:///jjit.sqlite3')
    parser.add_argument(
        '--verbose', action='store_true',
        help='verbose mode for debugging')
    parser.add_argument(
        '--dont-send', action='store_true',
        help='do not actually send offers via Telegram')

    args = parser.parse_args()

    if args.contract_type == 'ANY':
        args.contract_type = ''

    global VERBOSE
    VERBOSE = args.verbose

    engine = create_engine(args.database)
    metadata = MetaData()
    db = scoped_session(sessionmaker(
        autocommit=False, autoflush=True, bind=engine))

    if not sqlalchemy.inspect(engine).has_table(Offer.__tablename__):
        Offer.__table__.create(engine)

    jjit_api_request = requests.get(API_URL)
    all_incoming_offers = jjit_api_request.json()

    for incoming_offer in all_incoming_offers:
        parse_offer_from_api(incoming_offer, db)
    db.commit()

    for incoming_offer in all_incoming_offers:
        parse_multioffer_from_api(incoming_offer, db)
    db.commit()

    all_known_offers = get_all_known_offers(db, args)
    for known_offer in all_known_offers:
        offer_previously_sent = check_if_offer_sent(known_offer)
        if not offer_previously_sent:
            offer_matches = check_if_offer_matches(known_offer, args)
            if offer_matches:
                send_offer(known_offer, args.dont_send)
                mark_offer_as_sent(known_offer)
    db.commit()


if __name__ == '__main__':
    main()
