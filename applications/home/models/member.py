#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime
import uuid
import json
import os

from tornado.escape import json_decode

from applications.core.settings_manager import settings
from applications.core.cache import cache

from applications.core.logger.client import SysLogger
from applications.core.utils import Func
from applications.core.models import BaseModel

from sqlalchemy.types import Integer
from sqlalchemy.types import Numeric
from sqlalchemy.types import String
from sqlalchemy.types import Text
from sqlalchemy.types import TIMESTAMP
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import PrimaryKeyConstraint


class MemberOperationLog(BaseModel):
    """
    user model
    """
    __tablename__ = 'member_operation_log'

    uuid = Column(String(32), primary_key=True, nullable=False, default=Func.uuid32())
    user_id = Column(String(32), ForeignKey('member.uuid'))
    # 用户账号： email or mobile or username
    account = Column(String(80), nullable=False)
    # 会员操作类型： email_reset_pwd mobile_reset_pwd username_reset_pwd activate_email
    action = Column(String(20), nullable=False)
    ip = Column(String(40), nullable=False)
    client = Column(String(20), nullable=True, default='web')
    utc_created_at = Column(TIMESTAMP, default=Func.utc_now)

    @property
    def created_at(self):
        return Func.dt_to_timezone(self.utc_created_at)

    @staticmethod
    def add_log(params):
        """激活邮件

        [description]

        Arguments:
            params {[type]} -- [description]
        """
        log = MemberOperationLog(**params)
        MemberOperationLog.session.add(log)
        MemberOperationLog.session.commit()

class MemberLoginLog(BaseModel):
    """
    user model
    """
    __tablename__ = 'member_login_log'

    uuid = Column(String(32), primary_key=True, nullable=False, default=Func.uuid32())
    user_id = Column(String(32), ForeignKey('member.uuid'))
    ip = Column(String(40), nullable=False)
    client = Column(String(20), nullable=True, default='web')
    utc_created_at = Column(TIMESTAMP, default=Func.utc_now)

    @property
    def created_at(self):
        return Func.dt_to_timezone(self.utc_created_at)

class Member(BaseModel):
    """
    user model
    """
    __tablename__ = 'member'

    uuid = Column(String(32), primary_key=True, nullable=False, default=Func.uuid32())
    password = Column(String(128), nullable=False, default='')
    username = Column(String(40), nullable=False)
    mobile = Column(String(11), nullable=True)
    email = Column(String(80), nullable=True)
    level_id = Column(Integer, nullable=False, default=0)
    # 经验值
    experience = Column(Integer, nullable=False, default=0)
    # 性别(男 male ，女 female 隐藏 hide)
    sex = Column(String(10), nullable=False, default='hide')
    # 头像
    avatar = Column(String(255), nullable=True, default='')
    # 签名
    sign = Column(String(255), nullable=True, default='')
    login_count = Column(Integer, nullable=False, default=0)
    last_login_ip = Column(String(40), nullable=False, default='')
    deleted = Column(Integer, nullable=False, default=0)
    # 用户状态:(0 锁定, 1正常, 默认1)
    status = Column(Integer, nullable=False, default=1)
    utc_last_login_at = Column(TIMESTAMP, nullable=True)
    utc_created_at = Column(TIMESTAMP, default=Func.utc_now)
    ref_user_id = Column(String(32), default='')
    register_ip = Column(String(40), nullable=False, default='')
    # 客户端：web wechat android ios mobile
    register_client = Column(String(40), nullable=False, default='')

    sex_options = {
        'hide': '保密',
        'male': '男',
        'female': '女',
    }


    @property
    def sex_option(self):
        return self.sex_options.get(self.sex, '保密')


    @property
    def authorized(self):
        obj = MemberCertification.Q.filter(MemberCertification.user_id==self.uuid).first()
        # print('MemberCertification : ', MemberCertification.Q.statement)
        return True if obj and obj.authorized==1 else False


    @property
    def authorize_info(self):
        return MemberCertification.Q.filter(MemberCertification.user_id==self.uuid).first()


    @property
    def last_login_at(self):
        return Func.dt_to_timezone(self.utc_last_login_at)


    @property
    def created_at(self):
        return Func.dt_to_timezone(self.utc_created_at)


    @property
    def email_activated(self):
        return self.check_email_activated(self.uuid, self.email)


    @staticmethod
    def sex_options_html(sex=''):
        html = '<option value="">请选择性别</option>'
        option = '<option value="%s" %s>%s</option>'
        for key in Member.sex_options:
            selected = 'selected="true"' if sex==key else ''
            html += option % (key, selected, Member.sex_options[key])
        # print("html", sex, html)
        return html


    def cache_info(self, handler):
        """cache member info"""
        fileds = ['uuid','username','mobile','avatar','sign']
        member_dict = self.as_dict(fileds)

        if not member_dict['username']:
            member_dict['username'] = member_dict.get('mobile', '--')
        avatar = member_dict.get('avatar', None)
        if avatar:
            member_dict['avatar'] = handler.static_url(member_dict['avatar'])
        else:
            member_dict['avatar'] = handler.static_url('image/default_avatar.jpg')
        cache_key = '%s%s' % (settings.member_cache_prefix, self.uuid)
        cache.set(cache_key, member_dict, timeout=86400)
        return cache_key


    @staticmethod
    def get_info(user_id, fields='username,avatar,sign', scalar=False):
        query = "select %s from member where uuid='%s'" % (fields, user_id, )
        info = Member.session.execute(query).first()
        # print("info2", info)
        info = dict(info) if info else {}
        return info.get(fields, '') if scalar is True else info


    @staticmethod
    def check_email_activated(user_id, email):
        query = "select count(*) from member_operation_log where user_id='%s' and account='%s' and action='activate_email'" % (user_id, email)
        # print("query: ", query)
        value = Member.session.execute(query).scalar()
        return True if value>0 else False


    @staticmethod
    def _friend_list(user_id, where=''):
        query = "select m.uuid as user_id,m.username,m.avatar,m.sign,f.group_id from member m left join member_friend f on m.uuid=f.to_user_id where f.from_user_id='%s' and m.status=1 and f.status=1 %s" % (user_id, where)
        rows = Member.session.execute(query).fetchall()
        items = []
        if rows:
            for row in rows:
                items.append(dict(row))
        return items


    @staticmethod
    def friends_no_grouping(user_id):
        where = " and f.group_id='0'"
        return Member._friend_list(user_id, where)


    @staticmethod
    def friends_by_group(user_id, static_url):
        """
        按分组获取好友
        """
        _friend_list = Member._friend_list(user_id)
        # print('_friend_list: ', _friend_list)
        query = "select uuid, groupname from member_friendgroup where owner_user_id='%s'" % user_id
        grows = Member.session.execute(query).fetchall()
        grows = grows if grows else []
        # print("grows: ", type(grows), grows)
        f_g_li = []
        try:
            if len(grows)>0:
                f_g_li += [{
                    'id': group_id,
                    'groupname': groupname,
                    'list':[{
                        'id':fnd.get('user_id'),
                        'username':fnd.get('username'),
                        'status': Online.get_online(fnd.get('user_id')),
                        'sign':fnd.get('sign'),
                        'avatar':fnd.get('avatar')
                    } for fnd in _friend_list if fnd.get('group_id')==group_id
                ]} for (group_id, groupname) in grows]

            # Member.friends_no_grouping(user_id)
            f_g_li += [{'id': '0', 'groupname': '未分组', 'list':[{
                'id':fnd.get('user_id'),
                'username':fnd.get('username'),
                'status': Online.get_online(fnd.get('user_id')),
                'sign':fnd.get('sign'),
                'avatar':static_url(fnd.get('avatar'))
            } for fnd in Member.friends_no_grouping(user_id)]}]
        except Exception as e:
            raise e

        return f_g_li


    @staticmethod
    def login_success(member, handler, client='web'):
        # 设置登录用户cookiex信息
        handler.set_curent_user(member)

        user_id = member.uuid
        login_count = member.login_count if member.login_count else 0
        params = {
            'login_count': login_count+1,
            'utc_last_login_at': Func.utc_now(),
            'last_login_ip': handler.request.remote_ip,
        }
        Member.Q.filter(Member.uuid==user_id).update(params)

        # 写登录日志
        params2 = {
            'uuid': Func.uuid32(),
            'user_id': user_id,
            'client': client,
            'ip': handler.request.remote_ip,
        }
        log = MemberLoginLog(**params2)
        MemberLoginLog.session.add(log)

        MemberLoginLog.session.commit()

    @staticmethod
    def register(params):
        """用户注册事务"""
        try:
            user_id = Func.uuid32()
            params['uuid'] = user_id
            member = Member(**params)
            Member.session.add(member)

            Member.session.commit()
            return (0, member)
        except Exception as e:
            Member.session.rollback()
            SysLogger.info(e)
            return (500, str(e))

class MemberFriend(BaseModel):
    """
    user model
    """
    __tablename__ = 'member_friend'

    uuid = Column(String(32), primary_key=True, nullable=False, default=Func.uuid32())
    user_id = Column(String(32), ForeignKey('member.uuid'))
    ip = Column(String(40), nullable=False)
    client = Column(String(20), nullable=True, default='web')
    utc_created_at = Column(TIMESTAMP, default=Func.utc_now)

    @property
    def created_at(self):
        return Func.dt_to_timezone(self.utc_created_at)

class Online:
    cache_key = 'member_online:%s'

    @classmethod
    def get_online(cls, user_id):
        """
        获取用户在线状态
        """
        # state = redis_conn.get(cls.cache_key % (str(user_id),))
        # return state.decode() if state else 'offline'
        return 'online'


    @staticmethod
    def check_online(cls, user_id):
        pass


    @classmethod
    def set_online(cls, user_id, state):
        """
        设置用户在线状态
        state : [hide|online|offline]
        """
        # return redis_conn.set(cls.cache_key % (str(user_id),), state)
        return True


class MemberCertification(BaseModel):
    """
    会员出售球币
    """
    __tablename__ = 'member_certification'
    user_id = Column(String(32), primary_key=True, nullable=False)
    realname = Column(String(40), nullable=False)
    idcardno = Column(String(40), nullable=False)
    idcard_img = Column(String(200), nullable=False, default='')
    # 认证状态:( 0 待审核；1 审核通过, 2 审核不通过)
    authorized = Column(Integer, nullable=False, default=0)
    # 审核管理员ID，user 表 uuid
    authorized_user_id = Column(String(32), nullable=False, default='')
    client = Column(String(20), nullable=True, default='web')
    ip = Column(String(40), nullable=False)
    utc_updated_at = Column(TIMESTAMP, default=None)
    utc_created_at = Column(TIMESTAMP, default=Func.utc_now)
    # 状态:( 0 禁用；1 启用, 默认1)
    status = Column(Integer, nullable=False, default=1)
    # 备注；如果审核不通过，填写原因
    remark = Column(String(200), nullable=False)

    authorized_options = {
        0: '待审核',
        1: '审核通过',
        2: '审核不通过',
    }

    @property
    def authorized_option(self):
        return self.authorized_options[self.authorized]


    @property
    def updated_at(self):
        return Func.dt_to_timezone(self.utc_updated_at)
    @property
    def created_at(self):
        return Func.dt_to_timezone(self.utc_created_at)
