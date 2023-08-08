#!/bin/bash

# Установка screen
sudo apt install -y screen

# Установка Python 3.11 и необходимых пакетов
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-dev python3.11-gdbm python3.11-venv
sudo apt install -y curl gcc
curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python3.11

# Установка git
sudo apt install -y git

# Скачивание FunPayCardinal
git clone https://github.com/menleev/FixFunpayCardinal.git

# Переход в папку FixFunPayCardinal
cd FixFunPayCardinal

# Установка нужных пакетов
python3.11 setup.py

# Создание нового сеанса screen с названием "funpay"
screen -dmS funpay

# Отправка команды в сеанс screen для запуска FunPay Cardinal
screen -S funpay -X stuff "cd $(pwd)$(printf \\r)"
screen -S funpay -X stuff "python3.11 main.py$(printf \\r)"

echo "FunPay Cardinal установлен и запущен в сеансе 'funpay'."
