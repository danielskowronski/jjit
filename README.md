# jjit - check for newest justjoin.it job offers and push them by telegram_send

## requirements
* python3
* properly configured [telegram_send](https://pypi.org/project/telegram-send/#installation)
* some witable file to store processed offers

## usage
```
usage: jjit.py [-h] -c C [C ...] -l L [L ...] [-r]

jjit.py -- check for newest justjoin.it job offers and push them by
telegram_send

optional arguments:
  -h, --help    show this help message and exit
  -c C [C ...]  categories (like devops, java, c)
  -l L [L ...]  locations - cities
  -r            allow remote locations
```

example: `./jjit.py -l Kraków -c devops other -r`