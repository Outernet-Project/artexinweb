#!/usr/bin/env bash

# setup.sh: Prepare vagrant box for testing artexin code
#
# author: 	Outernet Inc <branko@outernet.is>
# version: 	0.1
#
# Copyright 2014, Outernet Inc.
# Some rights reserved.
# 
# This software is free software licensed under the terms of GPLv3. See COPYING
# file that comes with the source code, or http://www.gnu.org/licenses/gpl.txt.
#


set -e  # Halt on all errors

EI="easy_install -q"
SRCDIR=/vagrant
BINDIR=/usr/local/bin
ARFILE=/var/artexin

# Update local package DB and upgrade installed packages
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get -y upgrade

# Install build requirements
DEBIAN_FRONTEND=noninteractive apt-get -y install build-essential python \
  python-setuptools python-dev python-lxml libjpeg8 libjpeg8-dev zlib1g \
  zlib1g-dev libfreetype6-dev liblcms2-dev libwebp-dev tcl8.5-dev tk8.5-dev \
  python-tk phantomjs

# Setup Python libraries
echo "Installing dependencies"
$EI pip
pip install -r "$SRCDIR/requirements.txt"
pip install -r "$SRCDIR/dev_requirements.txt"

# Install NLTK data files
echo "Installing NLTK corpus data (please be patient)"
python -m nltk.downloader all

# Set up the runtest script
echo "Set up scripts"
if [[ ! -f "$BINDIR/runtests" ]]; then
	ln -s $SRCDIR/scripts/runtests.sh /usr/local/bin/runtests
fi

# Add /usr/local/bin to vagrant user's PATH
if [[ ! -f "${ARFILE}_0.1" ]]; then
	echo 'export PATH=$PATH:/usr/local/bin' >> /home/vagrant/.bashrc
	touch "${ARFILE}_0.1"
fi

# Create and start PhantomJS WebDriver service on port 8910
if [[ ! -f "/etc/init/phantom.conf" ]]; then
cat > /etc/init/phantom.conf <<EOF
start on started networking
stop on shutdown
exec /usr/bin/phantomjs --webdriver=127.0.0.1:8910
EOF
fi
service phantom start
