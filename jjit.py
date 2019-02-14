#!/usr/bin/python3
# -*- coding: utf-8 -*-

import requests, telegram_send, argparse

parser = argparse.ArgumentParser(description='jjit.py -- check for newest justjoin.it job offers and push them by telegram_send')
parser.add_argument('-c', nargs='+', help='categories (like devops, java, c)', required=True)
parser.add_argument('-l', nargs='+', help='locations - cities', required=True)
parser.add_argument('-r', action='store_true', help='allow remote locations')
args = parser.parse_args()

f = open('/tmp/jjit.txt','a+')
idsProcessed=open('/tmp/jjit.txt','r+').read()

r = requests.get('https://justjoin.it/api/offers')
offers = r.json()

for offer in offers:
	if offer['id'] in idsProcessed:
		continue

	categorised=False
	for category in args.c:
		if offer['marker_icon']==str(category):
			categorised=True
	
	localised=False
	if args.r and offer['remote']:
		localised=True
	for city in args.l:
		if offer['city']==str(city):
			localised=True

	if categorised and localised:
		msg=str(offer['company_name']+" - "+offer['title']+" https://justjoin.it/offers/"+offer['id'])
		print(msg)
		telegram_send.send(messages=[msg], parse_mode="markdown")
		f.write(","+offer['id'])

f.close()