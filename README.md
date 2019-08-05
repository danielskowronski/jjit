# jjit - check for newest justjoin.it job offers and push them by telegram_send

## requirements
* python3
* properly configured [telegram_send](https://pypi.org/project/telegram-send/#installation)
* some witable file to store processed offers (defaulted to /tmp/jjit.txt)

## usage
```
usage: jjit.py [-h] -c C [C ...] -l L [L ...] [-r] [-f F]

jjit.py -- check for newest justjoin.it job offers and push them by telegram_send

optional arguments:
  -h, --help    show this help message and exit
  -c C [C ...]  categories (like devops, java, c)
  -l L [L ...]  locations - cities
  -r            allow remote locations
  -s [S]        minimum salary
  -f F          state file
```

Example: `./jjit.py -l Kraków -c devops other -r -s 15000` (this will get offers in Kraków plus remote ones in categories devops and other with minimum salary of 15k PLN).

You'll probably want to put it in crontab.
