#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse
import telegram_send
import requests
import sys
from pprint import pprint
from datetime import datetime

API_URL = 'https://justjoin.it/api/offers'
VERBOSE = True


def check_if_offer_already_checked(offer, offer_ids_processed):
    if VERBOSE:
        print(f">> check_if_offer_already_checked: {offer['id']}")
    return offer['id'] in offer_ids_processed


def store_offer_variants(offer, state_file):
    if VERBOSE:
        print(f">> store_offer_variants: {offer['id']}")

    if offer['multilocation']:
        for offer_variant in offer['multilocation']:
            if offer_variant['slug'] != offer['id']:
                store_offer_id(offer_variant['slug'], state_file)


def store_offer_id(id, state_file):
    if VERBOSE:
        print(f">> store_offer: {id}")
    state_file.write(','+id)


def check_if_offer_macthes(offer, args):
    if VERBOSE:
        print(f">> check_if_offer_macthes: {offer['id']}")

    matches = {
        'category': False,
        'fully_remote': False,
        'location': False,
        'remuneration': False,
    }

    for desired_category in args.category:
        if offer['marker_icon'] == desired_category:
            matches['category'] = True
            break

    if args.fully_remote:
        matches['fully_remote'] = \
            offer['workplace_type'] == 'remote' and \
            offer['remote_interview'] == True
    else:
        matches['fully_remote'] = True

    matches_location = {
        'country': False,
        'city': False
    }

    if args.location_country:
        for desired_country in args.location_country:
            if offer['location']['country_code'] == desired_country:
                matches_location['country'] = True
                break
    else:
        matches_location['country'] = True

    if args.location_city:
        for desired_city in args.location_city:
            if offer['location']['city'] == desired_city:
                matches_location['city'] = True
                break
    else:
        matches_location['city'] = True

    matches['location'] = \
        matches_location['country'] and \
        matches_location['city']

    for offered_employment_type in offer['employment_types']:
        matches_remuneration = {
            'contract_type': False,
            'details_disclosed': False,
            'currency': False,
            'amount': False
        }

        matches_remuneration['details_disclosed'] =  \
            offered_employment_type['salary'] != None and  \
            offered_employment_type['salary']['to'] != None

        if not matches_remuneration['details_disclosed']:
            break  # breaking because other detail fields would be missing

        matches_remuneration['contract_type'] = \
            args.contract_type in offered_employment_type['type']

        matches_remuneration['currency'] = \
            offered_employment_type['salary']['currency'] == args.currency

        matches_remuneration['amount'] = int(
            offered_employment_type['salary']['to']) >= args.salary

        matches['remuneration'] = \
            matches_remuneration['details_disclosed'] and \
            matches_remuneration['contract_type'] and \
            matches_remuneration['currency'] and \
            matches_remuneration['amount']

        if matches['remuneration']:
            break

    if VERBOSE:
        print(matches)

    return \
        matches['category'] and \
        matches['fully_remote'] and \
        matches['location'] and \
        matches['remuneration']


def get_offer_url(offer):
    return 'https://justjoin.it/offers/'+offer['id']


def print_offer(offer):
    if VERBOSE:
        print(f">> print_offer: {offer['id']}")

    print('Matched offer: '+get_offer_url(offer))


def send_offer(offer):
    if VERBOSE:
        print(f">> send_offer: {offer['id']}")

    msg = offer['company_name']+' - '+offer['title']+' '+get_offer_url(offer)
    telegram_send.send(messages=[msg], parse_mode='markdown')


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
        '--state-file', default='/tmp/jjit.txt',
        help='state file; default - /tmp/jjit.txt')
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
        now = datetime.now()
        print(f"\n\n========================================================= {now}")
        print(f">> args:")
        pprint(args)

    state_file = open(args.state_file, 'a+')
    offer_ids_processed = open(args.state_file).read()

    jjit_api_request = requests.get(API_URL)
    all_offers = jjit_api_request.json()

    if VERBOSE:
        print("\n>> main/before_multioffer_check")

    if not args.location_city:
        offers_to_check = []
        for offer in all_offers:
            if VERBOSE:
                print(f"\n>> main/before: {offer['id']}")
            offer_already_checked = check_if_offer_already_checked(
                offer, offer_ids_processed)
            if not offer_already_checked:
                offers_to_check.append(offer)
                store_offer_variants(offer, state_file)

        state_file.close()
        state_file = open(args.state_file, 'a+')
        offer_ids_processed = open(args.state_file).read()
    else:
        offers_to_check = all_offers

    if VERBOSE:
        print("\n>> main/after_multioffer_check")

    for offer in offers_to_check:
        if VERBOSE:
            print(f"\n>> main/main: {offer['id']}")

        offer_already_checked = check_if_offer_already_checked(
            offer, offer_ids_processed)
        if not offer_already_checked:
            store_offer_id(offer['id'], state_file)

            offer_matches = check_if_offer_macthes(offer, args)
            if offer_matches:
                print_offer(offer)
                if not args.dont_send:
                    send_offer(offer)

    state_file.close()


if __name__ == '__main__':
    main()
