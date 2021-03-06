import threading
import requests
import hashlib
import base64
from v_code import v_code_idetify as v_code_
import json
import datetime
import pymysql
import dateutil.relativedelta as date_process
from ignore import db_config as config


class Crawler(threading.Thread):
    def __init__(self, thread_name, username, pwd, lock):
        threading.Thread.__init__(self)
        self.thread_name = thread_name
        self.username = username
        self.pwd = pwd
        self.lock = lock

    v_code_url = 'http://www.sinopecsales.com/websso/YanZhengMaServlet'
    post_login_url = 'http://www.sinopecsales.com/websso/loginAction_login.json'
    user_basic_info_url = 'http://www.sinopecsales.com/gas/webjsp/billQueryAction_queryBalance.json'
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,pt;q=0.7,zh-TW;q=0.6,ms;q=0.5,mt;q=0.4',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Host': 'www.sinopecsales.com',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36'
    }

    headers2 = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,pt;q=0.7,zh-TW;q=0.6,ms;q=0.5,mt;q=0.4',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Host': 'www.sinopecsales.com',
        'Origin': 'http://www.sinopecsales.com',
        'Referer': 'http://www.sinopecsales.com/gas/webjsp/query/billDetail.jsp',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.84 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest'
    }

    card_no = ''

    @staticmethod
    def __connect_db2():
        """
        ???????????????
        :return:
        """
        try:
            db = pymysql.connect(host=config.db_config['host'], port=config.db_config['port'], user=config.db_config['user'],
                                 passwd=config.db_config['pwd'], db=config.db_config['db'], charset='utf8')
            return db
        except Exception as e:
            print(e)
            exit()

    def simulate_login2(self, session, n=5):
        """
        ????????????
        :param session:
        :param n:?????????n???????????????
        :return:
        """
        i = 0
        while i < n:
            print('%s ?????????????????????..........' % self.thread_name)
            v_code_content = session.get(self.v_code_url, headers=self.headers).content
            base_64_content = base64.b64encode(v_code_content)
            print('%s ?????????????????????.............' % self.thread_name)
            v_code_o = v_code_.IdentifyVCode(base_64_content)
            v_code2 = v_code_o.return_identify_res()
            # ??????????????????????????? ??????????????????????????????
            if not v_code2:
                continue
            post_data = {
                'memberAccount': str(self.username),
                'memberUmm': hashlib.sha1(self.pwd.encode('utf-8')).hexdigest(),
                'check': v_code2,
                'rememberMe': 'on'
            }
            print('%s ??????????????????????????????????????????..........' % self.thread_name)
            login = session.post(self.post_login_url, headers=self.headers, data=post_data)
            if json.loads(login.text)['success'] == 0:
                print('%s ????????????!!!!!!!!!!' % self.thread_name)
                break
            i += 1

    def set_card_no(self, card_no):
        self.card_no = card_no
        return self

    def scrape_oil_card(self, session):
        """
        ???????????????????????????
        :param session:
        :return:
        """
        target_url = 'http://www.sinopecsales.com/gas/webjsp/billQueryAction_queryBalance.json'
        try:
            print("%s are getting oil_card" % self.thread_name)
            text = session.get(target_url, headers=self.headers).text
            self.set_card_no(json.loads(text)['cardInfo']['cardNo'])
            # return json.loads(text)['cardInfo']['cardNo']
        except Exception as e:
            print('suck me')
            print(e)
            exit()

    def scrape_trade_detail_by_month2(self, session, months):
        """
        ??????????????????????????????
        :param session: str
        :param months: list
        :return:
        """
        form1 = {'cardMember.cardNo': self.card_no}
        url1 = 'http://www.sinopecsales.com/gas/webjsp/billQueryAction_getCardInfoObject.json'
        print('%s ???????????????????????????????????????...........' % self.thread_name)
        session.post(url1, data=form1, headers=self.headers2)
        form4 = {'cardMember.cardNo': self.card_no, 'startTime': '', 'traType': False, 'dateFlag': False}
        url4 = 'http://www.sinopecsales.com/gas/webjsp/billQueryAction_transactionLog.json'

        for month in months:
            form4['startTime'] = month
            print('??????' + str(month) + '???????????????????????????......')
            res4 = session.post(url4, data=form4, headers=self.headers2).text
            res4_dic = json.loads(res4)
            # ?????????
            holders = res4_dic['holders']
            card_no = res4_dic['no']
            db = self.__connect_db2()
            cursor = db.cursor()
            print('????????????' + str(month) + '????????????????????????!--------------------------------')
            # ??????
            print('%s??????????????????????????????????????????' % self.thread_name)
            # ?????????????????????
            if not res4_dic['list']:
                continue
            self.lock.acquire()
            for i in res4_dic['list']:
                # ????????????
                amount = str(int(i['amount']) / 100 if int(i['amount']) != 0 else 0)
                # ????????????
                liter = str(int(i['litre']) / 100 if int(i['litre']) != 0 else 0)
                # ??????
                price = str(int(i['price']) / 100 if int(i['price']) != 0 else 0)
                # ????????????
                reward = str(i['reward'] / 100 if int(i['reward']) != 0 else 0)
                # ??????
                balance = str(int(i['balance']) / 100 if int(i['balance']) != 0 else 0)
                # ????????????
                now_ = str(datetime.datetime.today())[:19]
                # ????????????sql
                insert_sql = "INSERT INTO `la_zsh_trade_detail` (`card_no`,`card_owner`,`trade_time`,`trade_type`,`amount`,`oil_type`,`oil_num`,`price`,`reward_point`,`balance`,`location`,`created_at`) VALUES ('" + str(
                    card_no) + "','" + holders + "','" + i['opeTime'] + "','" + i['traName'] + "'," + amount + ",'" + i[
                                 'oilName'] + "'," + liter + "," + price + "," + reward + "," + balance + ",'" + i[
                                 'nodeTag'] + "','" + now_ + "')"
                try:
                    cursor.execute(insert_sql)
                    db.commit()
                except Exception as e:
                    print('fuck u')
                    print(e)
                    exit()
            print('%s????????????......' % self.thread_name)
            self.lock.release()

    @staticmethod
    def process_recent_months(date, n=3):
        """
        ?????????????????????
        :param date:
        :param n:
        :return:
        """
        tmp_date_list = [date]
        tmp_year_month_list = [str(date)[:7]]
        for i in range(n):
            tmp_d = tmp_date_list[0] - date_process.relativedelta(months=1)
            tmp_date_list.pop()
            tmp_date_list.append(tmp_d)
            tmp_year_month_list.append(str(tmp_d)[:7])
        del tmp_date_list
        return tmp_year_month_list

    def main_action2(self):
        # ??????session
        s = requests.session()
        # ????????????
        self.simulate_login2(s)
        # ??????????????????
        self.scrape_oil_card(s)
        # ????????????4???????????????
        months_list = self.process_recent_months(datetime.datetime.strptime('2018-01-01', '%Y-%m-%d'))
        # ??????????????????
        self.scrape_trade_detail_by_month2(s, months_list)
        # ??????????????????
        # self.scrape_top_up_detail(s, '2017-10-01', '2018-01-06')
        print('%s done!!!!!!!!!!!!!!!!!!!' % self.thread_name)

    def run(self):
        self.main_action2()


login_info_list = [
    ['TH1', 'Uc865a2df1ae27731', 'Uc355a2d'],
    ['TH2', 'youka66666', 'abcd123@'],
    ['TH3', 'Uc245a2def96d59ff', 'Uc915a2d'],
    ['TH4', 'Uc775a2defc36b0ec', 'Uc265a2d'],
    ['TH5', 'Uc315a2defd3f382b', 'Uc525a2d']
]
queue_lock = threading.Lock()
threads = []
# ???????????????
for i in login_info_list:
    thread_ = Crawler(i[0], i[1], i[2], queue_lock)
    thread_.start()
    threads.append(thread_)

for t in threads:
    t.join()

print('!!!!!!!!!!!!!!!!!!!!!!??????????????????!!!!!!!!!!!!!!!!!!!!!!')
