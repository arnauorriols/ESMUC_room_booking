#!/usr/bin/env python
# coding=utf-8

# Python prototipe for an Android app to automatize login and room
# reservation of the Escola Superior de Musica de Catalunya - Asimut
# system.
#
# Copyright 2013 Arnau Orriols. All Rights Reserved.

import requests
import time
import lxml.html as lxml
from sys import argv, exit


class AsimutSession (object):

    BASE_URL = "https://esmuc.asimut.net/public/"
    SERVER_CALLS = {'login' : 'login.php',
                    'book' : 'async-event-save.php',
                    'cancel' : 'async-event-cancel.php',
                    'fetch events' : 'async_fetchevents.php',
                    'index' : 'index.php',
                    'event info' : 'async-eventinfo.php'
    }

    LOCATIONGROUPS_ID = {'cabina' : '6',
                          'instrument individual' : '5',
                          'cambra' : '4',
                          'col·lectiva' : '3',
                          'aules de concert' : '12',
                          'improvisació' : '13',
                          'pianistes' : '11',
                          'musica antiga' : '9',
                          'jazz i mm' : '7',
                          'percussió' : '10',
                          'audiovisuals' : '14',
                          'informàtica' : '15',
                          'aules especifiques' : '18'}

    LOCATIONS_ID = {str(grupid) : {} for grupid in
    LOCATIONGROUPS_ID.itervalues()}

    LOCATIONS_ID[LOCATIONGROUPS_ID['pianistes']].update({
        "A%i" %room : str(ref) for room, ref
                               in zip(range(339, 344), range(73, 78))
    })
    LOCATIONS_ID[LOCATIONGROUPS_ID['cabina']].update({
        "C%i" %room : str(ref) for room, ref
                               in zip(range(102, 119), range(94, 111))
    })
    LOCATIONS_ID[LOCATIONGROUPS_ID['instrument individual']].update({
        "A%i" %room : str(ref) for room, ref
                               in zip(range(119, 121), range(19, 21))
    })
    LOCATIONS_ID[LOCATIONGROUPS_ID['instrument individual']].update({
        "A125" : "26", "A126" : "25"})
    LOCATIONS_ID[LOCATIONGROUPS_ID['instrument individual']].update({
        "A%i" %room : str(ref) for room, ref
                               in zip(range(301, 337), range(35, 71))
                               if room not in range(304, 322)
    })
    LOCATIONS_ID[LOCATIONGROUPS_ID['cambra']].update({
        "A%i" %room : str(ref) for room, ref
                              in zip(range(304, 339), range(38, 73))
                              if (room not in range(308, 314) and
                                  room not in range(316, 318) and
                                  room not in range(319, 337)
                              )
    })


    def login(self, user, password):

        payload = {'authenticate-useraccount' : user,
                   'authenticate-password' : password}
        url = "%s%s" % (self.BASE_URL, self.SERVER_CALLS['login'])

        self.requests_session = requests.session()
        self.requests_session.cookies = \
        requests.cookies.cookiejar_from_dict({'asimut-width' : '640'})
        self.requests_session.post(url, data=payload).content


    def fetch_booked_list(self):

        self.update_current_time_availability()
        payload = {'dato' : self.current_time_availability['start']['date'],
                   'akt' : 'visegne'
        }

        url = "%s%s" % (self.BASE_URL, self.SERVER_CALLS['index'])
        response = self.requests_session.get(url, params=payload).text

        parsed_html = lxml.document_fromstring(response)

        self.own_books_id = [{'room' : Node.getnext().text_content(),
                              'book_id' : Node.attrib['rel'],
                              'time' : Node.getparent().getparent()
                                           .getparent().getprevious()
                                           .text_content()}
                             for Node in parsed_html.find_class('event-link')]

        print self.own_books_id


    def book_room(self, room, date, starttime, endtime, description=''):

        room_id = self.find_room_id_by_name(room)
        roomgroup = self.find_roomgroup_by_room_id(room_id)

        payload = {'event-id' : '0',
                   'location-id' : room_id,
                   'date' : date,
                   'starttime' : starttime,
                   'endtime' : endtime,
                   'location' : room,
                   'description' : description
        }

        url = "%s%s" % (self.BASE_URL, self.SERVER_CALLS['book'])
        self.requests_session.post(url, data=payload)

    def fetch_unavailability(self, date, roomgroup_id):

        url = "%s%s" % (self.BASE_URL, self.SERVER_CALLS['fetch events'])
        date = "-".join(reversed(date.split('/')))
        payload = {'starttime' : date,
                   'endtime' : date,
                   'locationgroup' : "-%s" % roomgroup_id
        }

        response = self.requests_session.get(url, params=payload).json()

        url = "%s%s" % (self.BASE_URL, self.SERVER_CALLS['event info'])
        booksrooms_id = [(book[0], book[3]) for book in response]
        books_times = []

        for book_id, room_id in booksrooms_id:
            payload = {'id' : book_id}
            book_info = self.requests_session.get(url, params=payload).content
            book_info = lxml.fragment_fromstring(book_info)
            parsed_time = book_info[0].text_content().split(' ')
            books_times.append({'book_id' : book_id,
                                'room_id' : room_id,
                                'start' : parsed_time[0],
                                'end' : parsed_time[-1]})

        return books_times


    def get_last_book_id(self):

        self.fetch_booked_list

        return sorted([book_record['book_id']
                       for book_record in self.own_books_id])[-1]


    def cancel_book(self, book_id):

        payload = {'id' : book_id}
        url = "%s%s" % (self.BASE_URL, self.SERVER_CALLS['cancel'])

        response = self.requests_session.get(url, params=payload).json()
        return response

    def find_room_id_by_name(self, room_name):

        for room_group in self.LOCATIONGROUPS_ID.itervalues():
            if room_name in self.LOCATIONS_ID[room_group].keys():
                return self.LOCATIONS_ID[room_group][room_name]

        exit("Room doesn't exist")

    def find_roomgroup_by_room_id(self, room_id):

        for room_group in self.LOCATIONGROUPS_ID.itervalues():
            if room_id in self.LOCATIONS_ID[room_group].values():
                return room_group
        exit("Error")

    def update_current_time_availability(self):

        start_secs = time.time()
        threshold = 93600
        end_secs = start_secs + threshold
        start_time = time.localtime(start_secs)
        end_time = time.localtime(end_secs)
        self.current_time_availability = {
                'start' : {'date' : "%i%.2i%.2i" % start_time[0:3],
                           'time' : "%.2i:%.2i" % start_time[3:5],
                           'secs' : start_secs},
                'end' : {'date' : "%i%.2i%.2i" % end_time[0:3],
                         'time' : "%.2i:%.2i" % end_time[3:5],
                         'secs' : end_secs}
        }

if __name__ == "__main__":

    if len(argv) == 8:
        Session = AsimutSession()
        Session.login(argv[1], argv[2])
        Session.fetch_booked_list()
        Session.book_room(argv[3], argv[4],
                                    argv[5], argv[6],
                                    argv[7]
        )
        Session.fetch_booked_list()
        print Session.cancel_book(Session.get_last_book_id())
        Session.fetch_booked_list()
        print Session.current_time_availability
        print Session.fetch_unavailability(argv[4], '5')
    else:
        print "\nUsage: '$ python prototype.py <username> <password> " \
              "<room(ex:'A340')> <day(ex:'1/10/2013')> " \
              "<start_time (ex:'21:00')> <end_time(ex:'21:30')> " \
              "<description>"
