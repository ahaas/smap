import time
import urllib
from xml.etree import ElementTree

FAA_URL = ('http://services.faa.gov/airport/status/{}'
           + '?format=application/xml')
DELAY_TYPES = {
    'Ground Delay': '/delay/ground'
}
DIR_TO_ANG = {
    'North': 0,
    'Northeast': 45,
    'East': 90,
    'Southeast': 135,
    'South': 180,
    'Southwest': 225,
    'West': 270,
    'Northwest': 315,
}

from smap import driver, util

class FAADriver(driver.SmapDriver):
    def setup(self, opts):
        self.add_timeseries('/weather/temp', 'F', data_type='double')
        self.add_timeseries('/weather/visibility', 'miles',
                            data_type='double')
        self.add_timeseries('/weather/wind/speed', 'mph',
                            data_type='double')
        self.add_timeseries('/weather/wind/direction', 'degrees')

        self.add_timeseries('/delay/ground', 'minutes')

        # International Association of Travel Agents Airport Code
        self.iata = opts.get('iata')

    def start(self):
        util.periodicSequentialCall(self.read).start(60)

    def read(self):
        try:
            xmlstr = urllib.urlopen(FAA_URL.format(self.iata)).read()
            root = ElementTree.fromstring(xmlstr)
        except:
            print('FAA sMAP Driver error: Unexpected response! '
                  + 'Could not parse XML.')
            return

        def nav(tree, *args):
            for arg in args:
                tree = tree.find(arg)
                if tree is None:
                    return None
            return tree

        # Warn if expected keys are missing
        for key in [('Weather', 'Temp'),
                    ('Weather', 'Visibility'),
                    ('Weather', 'Wind'),
                    ('Status', 'Type'),
                    ('Status', 'AvgDelay')]:
            if nav(root, *key) is None:
                print('Warning: Expected key "{}" was not found!'
                      .format(key))

        # Temperature
        if nav(root, 'Weather', 'Temp') is not None:
            self.add('/weather/temp',
                     float(nav(root, 'Weather', 'Temp').text
                                                       .split()[0]))

        # Visibility
        if nav(root, 'Weather', 'Visibility') is not None:
            self.add('/weather/visibility',
                     float(nav(root, 'Weather', 'Visibility').text))

        # Wind direction and speed
        if nav(root, 'Weather', 'Wind') is not None:
            direction, speed = self._parse_wind(
                nav(root, 'Weather', 'Wind').text)
            self.add('/weather/wind/speed', speed)
            self.add('/weather/wind/direction', direction)

        if ((nav(root, 'Status', 'Type') is not None) and
            (nav(root, 'Status', 'AvgDelay') is not None)):

            # Delay for current delay type
            this_delay_type = nav(root, 'Status', 'Type').text
            if this_delay_type == 'Ground Delay':
                delaystr = nav(root, 'Status', 'AvgDelay').text
                self.add('/delay/ground', self._parse_avgdelay(delaystr))

            # All other delay types have value 0
            for delay_type in DELAY_TYPES:
                if delay_type != this_delay_type:
                    self.add(DELAY_TYPES[delay_type], 0)

    def _parse_wind(self, windstr):
        s = windstr.split()
        direction = DIR_TO_ANG[s[0]]
        speed = float(s[2][:-3])  # remove the 'mph'
        return direction, speed

    def _parse_avgdelay(self, delaystr):
        if not delaystr:
            return 0
        s = delaystr.split()
        if len(s) == 5:
            return int(s[0])*60 + int(s[3])
        else:
            return int(s[0])
