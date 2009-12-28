# -*- coding: utf8 -*-

try:
    from lalita import Plugin
except:
    from core import Plugin

import pywapi

TRANSLATION_TABLE = {
        u'La temperatura en %(city)s (%(forecast_date)s) es ' \
        u'%(temp_c)sC/%(temp_f)sF. Condiciones: %(condition)s. %(humidity)s. '\
        u'%(wind_condition)s.': {
                u'en': u'The temperature in %(city)s (%(forecast_date)s) is ' \
        u'%(temp_c)sC/%(temp_f)sF. Conditions: %(condition)s. %(humidity)s. '\
        u'%(wind_condition)s.', }
        }


class Weather(Plugin):
    '''The weather plugin reports the weather using pywapi.'''

    def init(self, config):
        self.logger.info("Init! config: %s", config)
        self.register(self.events.COMMAND, self.weather, ("weather",))
        self.register(self.events.COMMAND, self.forecast, ("forecast",))
        self.lang = "es"
        self.register_translation(self, TRANSLATION_TABLE)

    def weather(self, user, channel, command, *args):
        u'''@weather ciudad[,país]: reporta el clima.'''
        
        #from pudb import set_trace; set_trace()

        self.logger.debug("command %s from %s (args: %s)", command, user, args)

        if args:
            city = " ".join(args)
            data = pywapi.get_weather_from_google(city, self.lang)
            try:

                current_weather = data['current_conditions']
                current_weather.update(data['forecast_information'])
                txt = u'La temperatura en %(city)s (%(forecast_date)s) ' \
                       u'es %(temp_c)sC/%(temp_f)sF. Condiciones: ' \
                       u'%(condition)s. %(humidity)s. %(wind_condition)s.' \
                                % current_weather
                self.logger.debug(current_weather)
                self.logger.debug(type(txt))
            except Exception, e:
                txt = u'%s: No te quiero ofender pero... ¿Y eso dónde queda?'\
                        % (user,)
                self.logger.debug(e)
        else:
            txt = u'%s: Perdoná que me ponga filosófica pero si no hay ' \
                   u'lugar, no hay clima!' % user
        txt = txt.replace("%", "%%")
        self.say(channel, txt)

    def forecast(self, user, channel, command, *args):
        u'''@forecast ciudad[país]: pronóstico del clima.'''

        self.logger.debug("command %s from %s (args: %s)", command, user, args)
        
        #from pudb import set_trace; set_trace()
        
        if args:
            city = " ".join(args)
            data = pywapi.get_weather_from_google(city, self.lang)
            header = u'El pronóstico para %(city)s es: '
            template = u'%(day_of_week)s: %(condition)s, Máxima: %(high)s, Mínima: '\
                    u'%(low)s.'
            try:
                forecasts = [ template % j for j in data['forecasts'] ]
                txt = u'%s %s' % (header % data['forecast_information'], \
                        ' '.join(forecasts))
            except Exception, e:
                self.logger.debug('%s', e)
                txt = u'%s: No sé, fijate en el diario.' % user
        else:
            txt = u'%s: El pronóstico para nada, es nada.' % user
        self.say(channel, txt)
