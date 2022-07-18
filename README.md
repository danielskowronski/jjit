# jjit - check for newest justjoin.it job offers and push them by telegram_send

## requirements
* python3
* properly configured [telegram_send](https://pypi.org/project/telegram-send/#installation); e.g. at `/etc/telegram-send.conf`
* some witable file to store processed offers (defaulted to /tmp/jjit.txt)
* `python3 -m pip install -r requirements.txt`

## categories, currencies, contract types

As justjoin.it is evolving categories, currencies and contract types cannot just be put into enums. They are quite obvious in most cases, but to get all possible values you may run:

```bash
curl -s https://justjoin.it/api/offers > all.json
echo "== --category"
cat all.json | jq | grep '"marker_icon"' |sort | uniq -c | sort -rn
echo "== --currency"
cat all.json | jq | grep '"currency"' |sort | uniq -c | sort -rn
echo "== --contract-type"
cat all.json | jq | grep '"type"' |sort | uniq -c | sort -rn
``` 

## usage
```
usage: jjit.py [-h] --category CATEGORY [CATEGORY ...] [--fully_remote] [--location-country LOCATION_COUNTRY [LOCATION_COUNTRY ...]]
               [--location-city LOCATION_CITY [LOCATION_CITY ...]] [--salary [SALARY]] [--currency [CURRENCY]] [--contract-type [CONTRACT_TYPE]] [--state-file STATE_FILE]
               [--verbose] [--dont-send]

jjit.py -- check for newest justjoin.it job offers and push them by telegram_send

optional arguments:
  -h, --help            show this help message and exit
  --category CATEGORY [CATEGORY ...]
                        categories (like devops, java, c)
  --fully_remote        fully remote offer (i.e. remote interview + remote workplace
  --location-country LOCATION_COUNTRY [LOCATION_COUNTRY ...]
                        locations - countries; format - ISO 3166-1 alfa-2 (e.g. PL)
  --location-city LOCATION_CITY [LOCATION_CITY ...]
                        locations - cities
  --salary [SALARY]     minimum salary (assumed gross/month); default - 10000
  --currency [CURRENCY]
                        currency (as in offer) [pln, usd, eur, gbp, chf]; default - pln
  --contract-type [CONTRACT_TYPE]
                        contract type [permanent, b2b, mandate_contract, ANY]; default - ANY
  --state-file STATE_FILE
                        state file; default - /tmp/jjit.txt
  --verbose             verbose mode for debugging
  --dont-send           do not actually send offers via Telegram
```

Example: `python3 jjit.py --category devops admin support architecture other security --fully_remote --salary 22000`

You'll probably want to put it in crontab.

## debug

```
rm s.txt; curl -s https://justjoin.it/api/offers | jq > all.json; python3 jjit.py --category devops admin support architecture other security --fully_remote --salary 21000 --contract permanent --dont-send --verbose --state-file s.txt | tee r.txt; cat r.txt | grep "Matched offer" | wc -l
```
