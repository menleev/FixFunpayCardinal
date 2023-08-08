#!/bin/bash

# Установка screen
yes | sudo apt install -y screen

# Установка Python 3.11 и необходимых пакетов
yes | sudo apt update
yes | sudo apt install -y software-properties-common
yes | sudo add-apt-repository -y ppa:deadsnakes/ppa
yes | sudo apt update
yes | sudo apt install -y python3.11 python3.11-dev python3.11-gdbm python3.11-venv
yes | sudo apt install -y curl gcc
yes | curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python3.11

# Установка git
yes | sudo apt install -y git

# Скачивание FunPayCardinal
yes | git clone https://github.com/menleev/FixFunpayCardinal.git

# Переход в папку FixFunPayCardinal
cd /root/FixFunpayCardinal

# Установка нужных пакетов
yes | python3.11 ./setup.py

# Создание нового сеанса screen с названием "funpay"
screen -dmS funpay

# Отправка команды в сеанс screen для запуска FunPay Cardinal
screen -S funpay -X stuff "cd /root/FixFunpayCardinal$(printf \\r)"
screen -S funpay -X stuff "python3.11 main.py$(printf \\r)"

echo "FunPay Cardinal установлен и запущен в сеансе 'funpay'."
echo "Чтобы перейти в окно funpay наберите команду screen -x funpay"
