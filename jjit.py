#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse
import telegram_send
import requests
import sys
from pprint import pprint
from datetime import datetime
import orm_sqlite
import re

from datetime import datetime
programStartDate = datetime.now()

import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, event, MetaData
from sqlalchemy.orm import scoped_session, sessionmaker, backref, relation
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.automap import automap_base

import hashlib
import json

API_URL = 'https://justjoin.it/api/offers'
VERBOSE = True

def check_if_offer_matches(offer, args):
    if VERBOSE:
        print(f">> check_if_offer_macthes: {offer['id']}")

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


    if VERBOSE:
        print(matches)

    return \
        matches['category'] and \
        matches['fully_remote'] and \
        matches['location'] and \
        matches['remuneration']


def get_offer_url(offer):
    return 'https://justjoin.it/offers/'+offer.slug

def send_offer(offer, dont_send):
    msg = offer.company_name+' - '+offer.title+' '+get_offer_url(offer)
    print(msg)
    if not dont_send:
        telegram_send.send(messages=[msg], parse_mode='markdown')

Base = declarative_base()

class Offer(Base):  
    __tablename__ = 'offers'

    lastUpdated = Column('last_updated', DateTime)
    sent = Column(Boolean)

    parent = Column(String)
    slug = Column(String, primary_key=True)
    title = Column(String)
    company_name = Column(String)

    category = Column(String)

    workplace_remote = Column(Boolean)
    interview_remote = Column(Boolean)

    @property
    def fully_remote(self):
        return self.workplace_remote and self.interview_remote

    country_code = Column(String(2))
    city = Column(String)
    
    contract_type = Column(String, primary_key=True)
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    currency = Column(String(3))

    multiloc_checksum = Column(String)

def get_multilocChildOffers(multilocChildSlug, db):
    return db.query(Offer).filter(
        Offer.slug == multilocChildSlug, 
        Offer.parent == None
    )

def parse_multioffer_from_api(incomingOfferRaw, db):
    undisclosedSalary = not incomingOfferRaw['employment_types']
    if undisclosedSalary:
        return
    incomingOfferIsMultilocParent = incomingOfferRaw['multilocation'] and len(incomingOfferRaw['multilocation'])>1
    if not incomingOfferIsMultilocParent:
        return

    for incommingOfferEmploymentOption in incomingOfferRaw['employment_types']:
        if not incommingOfferEmploymentOption['salary']:
            return

        for multilocEntry in incomingOfferRaw['multilocation']:
            multilocChildSlug = multilocEntry['slug']
            multilocChildOffers = get_multilocChildOffers(multilocChildSlug, db)
            for multilocChildOffer in multilocChildOffers:
                multilocChildOffer.lastUpdated = programStartDate
                multilocChildOffer.parent      = incomingOfferRaw['id']

def hash_multiloc(multiloc):
    multiloc_slugs = []
    for multiloc_entry in multiloc:
        multiloc_slugs.append(multiloc_entry['slug'])
    multiloc_slugs.sort()
    return hashlib.md5(json.dumps(multiloc_slugs, sort_keys=True).encode('utf-8')).hexdigest()

def incomingOffer_from_raw(incomingOfferRaw, incommingOfferEmploymentOption):
    incomingOffer = Offer();
    incomingOffer.lastUpdated       = programStartDate
    incomingOffer.slug              = incomingOfferRaw['id']
    incomingOffer.contract_type     = incommingOfferEmploymentOption['type']
    incomingOffer.title             = incomingOfferRaw['title']
    incomingOffer.company_name      = incomingOfferRaw['company_name']
    incomingOffer.category          = incomingOfferRaw['marker_icon']
    incomingOffer.workplace_remote  = incomingOfferRaw['workplace_type']=='remote'
    incomingOffer.interview_remote  = incomingOfferRaw['remote_interview']
    incomingOffer.country_code      = incomingOfferRaw['country_code']
    incomingOffer.city              = incomingOfferRaw['city']
    incomingOffer.salary_min        = incommingOfferEmploymentOption['salary']['from']
    incomingOffer.salary_max        = incommingOfferEmploymentOption['salary']['to']
    incomingOffer.currency          = incommingOfferEmploymentOption['salary']['currency']
    incomingOffer.multiloc_checksum = hash_multiloc(incomingOfferRaw['multilocation'])
    return incomingOffer

def get_knownOffersMatchingIDs(incomingOffer, db):
    return db.query(Offer).filter(
        Offer.slug          == incomingOffer.slug, 
        Offer.contract_type == incomingOffer.contract_type, 
    )
def add_incomingOffer(incomingOffer, db):
    db.add(incomingOffer)
def delete_offer(offer, db):
    db.delete(offer)

def parse_offer_from_api(incomingOfferRaw, db):
    undisclosedSalary = not incomingOfferRaw['employment_types']
    if undisclosedSalary:
        return

    for incommingOfferEmploymentOption in incomingOfferRaw['employment_types']:
        if not incommingOfferEmploymentOption['salary']:
            return

        incomingOffer = incomingOffer_from_raw(incomingOfferRaw, incommingOfferEmploymentOption)

        knownOffersMatchingIDs = get_knownOffersMatchingIDs(incomingOffer, db)
        
        if knownOffersMatchingIDs.count()>1:
            raise Exception("len(offersAlreadyKnown)>1")

        offerAlreadyKnown = knownOffersMatchingIDs.count()==1
        
        knownOfferMatchingIDsChanged = False
        if offerAlreadyKnown:
            knownOfferMatchingIDs=knownOffersMatchingIDs[0]
            knownOfferMatchingIDsChanged = \
                incomingOffer.multiloc_checksum != knownOfferMatchingIDs.multiloc_checksum or \
                incomingOffer.title             != knownOfferMatchingIDs.title or \
                incomingOffer.category          != knownOfferMatchingIDs.category or \
                incomingOffer.workplace_remote  != knownOfferMatchingIDs.workplace_remote or \
                incomingOffer.interview_remote  != knownOfferMatchingIDs.interview_remote or \
                incomingOffer.salary_min        != knownOfferMatchingIDs.salary_min or \
                incomingOffer.salary_max        != knownOfferMatchingIDs.salary_max or \
                incomingOffer.currency          != knownOfferMatchingIDs.currency 
        
        if knownOfferMatchingIDsChanged:
            print("<-- changed: "+incomingOfferRaw['id'])
            delete_offer(knownOffersMatchingIDs[0], db)

        if not offerAlreadyKnown:
            add_incomingOffer(incomingOffer, db)

def check_if_offer_sent(offer):
    return offer.sent

def mark_offer_as_sent(offer):
    offer.sent = True

def get_all_known_offers(db, args):
    if not args.location_city or args.fully_remote:
        return db.query(Offer).filter(Offer.parent==None)
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

    if VERBOSE:
        print(f"\n\n========================================================= {programStartDate}")
        print(f">> args:")
        pprint(args)


    engine = create_engine(args.database) #,echo = True)
    metadata = MetaData()
    db = scoped_session(sessionmaker(autocommit=False,autoflush=True,bind=engine))

    if not sqlalchemy.inspect(engine).has_table(Offer.__tablename__):
        Offer.__table__.create(engine)

    jjit_api_request = requests.get(API_URL)
    all_incoming_offers = jjit_api_request.json()
    all_incoming_offers.sort(key=id)

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
