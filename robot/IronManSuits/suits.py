# coding=utf-8
import ConfigParser
import json
import logging
import urllib
from logging import config

import bs4
from sqlalchemy.exc import IntegrityError

from robot.IronManSuits.models.weather_data import WeatherData
from robot.weapons import data_miscs, db


class MarkI:
    def __init__(self, city_id, conf):
        self.city_id = city_id
        self.conf = conf
        self._raw_weather_data = None
        self.weather_data = []
        self.get_data()

    def __del__(self):
        pass

    def db_conn(self):
        """
        db orm 获取
        :return: 
        """
        # 初始化数据库连接:
        # defengine = create_engine(
        #     'mysql+mysqlconnector://{user}:{pwd}@{host}:3306/{db}'.format(user=user, pwd=password, host=host, db=db))
        # 创建DBSession类型:
        # DBSession = sessionmaker(bind=engine)
        pass

    def redis(self):
        """
        redis链接获取
        :return: 
        """
        return

    def get_data(self):
        """
        获取数据的方法 会循环尝试获取数次 在获取到数据后对数据进行提取和格式化
        :return: 
        """
        err_count = 0
        while not self._get_data() and err_count < self.conf.get('misc', 'max_err'):
            err_count += 1
        if err_count == self.conf.get('misc', 'max_err'):
            logging.error('[{city_id}]: error time over limit'.format(city_id=self.city_id))
            return False
        if '7d' not in self._raw_weather_data:
            logging.warning("[{city_id}]: weather_data don't have '7d' - {weather_data}".format(
                city_id=self.city_id,
                weather_data=self._raw_weather_data))
            return False
        self._raw_weather_data = self._raw_weather_data['7d']
        if not self._raw_weather_data:
            logging.error('[{city_id}]: error weather data - {weather_data}'.format(
                city_id=self.city_id,
                weather_data=self._raw_weather_data))
            return False
        if len(self._raw_weather_data) < 7:
            logging.error(
                '[{city_id}]: length of weather_data is error - {weather_data}'.format(
                    city_id=self.city_id,
                    weather_data=self._raw_weather_data))
            return False
        if self._raw_weather_data[0][0].count(',') < 5:
            logging.error("[{city_id}]: lack ',' in weather_data - {weather_data}".format(
                city_id=self.city_id,
                weather_data=self._raw_weather_data))
            return False

        for weather_lists in self._raw_weather_data:
            for weather in weather_lists:
                self.save_data(weather)
        return True

    def _get_data(self):
        """
        获取data的http请求基本方法
        :return: 
        """
        req = urllib.urlopen('http://www.weather.com.cn/weather/{city_id}.shtml'.format(city_id=self.city_id))
        if req.getcode() / 100 == 2:
            weather_html = bs4.BeautifulSoup(req.read(), 'html.parser')
            try:
                data = filter(lambda a: a.text.find('hour3data') > -1, weather_html.find_all('script'))[0].text
            except IndexError as e:
                logging.error(e)
                return None
            try:
                self._raw_weather_data = json.loads(data[data.find('{'):])
                return True
            except ValueError as e:
                logging.error(e)
                return None
            except TypeError as e:
                logging.error(e)
                return None
        else:
            logging.error(req.read(), req.getcode())
            return None

    def analyze(self):
        pass

    def get_web_weather_obj(self, raw_weather):
        weather = raw_weather.encode('utf8').split(',')
        weather_data = WeatherData()
        weather_data.city_id = self.city_id
        weather_data.weather_date = data_miscs.get_date(weather[0])
        weather_data.weather_time = data_miscs.get_time(weather[0])
        weather_data.cond = data_miscs.cond_str2int(weather[2])
        weather_data.temp = data_miscs.get_temp(weather[3])
        weather_data.wind_dir = data_miscs.wind_dir_dtr2int(weather[4])
        weather_data.wind_speed = data_miscs.wind_speed_str2int(weather[5])
        weather_data.meta = raw_weather.encode('utf8')
        return weather_data

    def get_db_weather_data(self, weather_obj):
        results = db.get_db_Session(self.conf).query(WeatherData).filter(
            WeatherData.city_id == weather_obj.city_id,
            WeatherData.weather_date == weather_obj.weather_date,
            WeatherData.weather_time == weather_obj.weather_time).all()
        if len(results) == 0:
            return None
        if len(results) != 1:
            logging.error([result.id for result in results])
        return results[0]

    def save_data(self, raw_weather):
        # session = db.get_db_Session(self.conf)
        web_weather_obj = self.get_web_weather_obj(raw_weather)
        db_weather_obj = self.get_db_weather_data(web_weather_obj)
        if db_weather_obj:
            self.compare_change(web_weather_obj, db_weather_obj)
            print db_weather_obj.meta
        try:
            # session.add(new_weather_obj)
            # session.commit()
            pass
        except IntegrityError as e:
            logging.error(e)

    def save_history(self):
        pass

    def start(self):
        pass

    def compare_change(self, web_weather_obj, db_weather_obj):
        if (web_weather_obj.city_id != db_weather_obj.city_id or
                    web_weather_obj.weather_date != db_weather_obj.weather_date or
                    web_weather_obj.weather_time != db_weather_obj.weather_time):
            logging.error('city_id错误')
        change_point = 0
        web_weather_obj.id = db_weather_obj.id
        return web_weather_obj, change_point


if __name__ == '__main__':
    # logging.basicConfig(
    #     level=logging.DEBUG,
    #     format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
    #     datefmt='%Y-%b-%d:%H:%M:%S',
    #     filname='robot_run_error.log',
    #     filemode='a+',
    #     disable_existing_loggers=0,
    #     maxbytes=0
    #
    # )
    logging.config.fileConfig('../config/log.conf')
    c = ConfigParser.ConfigParser()
    c.read('../config/config.ini')
    r = MarkI(101010300, c)
