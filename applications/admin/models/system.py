#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime
import uuid
import json

from applications.core.settings_manager import settings

from applications.core.db.dbalchemy import Model
from applications.core.utils import datetimezone
from applications.core.logger.client import SysLogger

from sqlalchemy.types import Integer
from sqlalchemy.types import String
from sqlalchemy.types import Text
from sqlalchemy.types import TIMESTAMP
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import PrimaryKeyConstraint

from applications.core.utils import utc_to_timezone
from applications.core.utils import uuid32

class BaseModel(Model):
    __abstract__ = True
    __connection_name__ = 'default'


class Config(BaseModel):
    """
    sys_config model
    """
    __tablename__ = 'sys_config'

    key = Column(String(40), primary_key=True, nullable=False)
    value = Column(String(80), nullable=False)
    remark = Column(String(128), nullable=False)
    # 状态:(0 无效, 1正常, 默认1)
    status = Column(Integer, nullable=False, default=1)
    utc_created_at = Column(TIMESTAMP, default=datetimezone)

    @property
    def created_at(self):
        return utc_to_timezone(self.utc_created_at)


class Role(BaseModel):
    """
    user model
    """
    __tablename__ = 'sys_admin_role'

    uuid = Column(String(32), primary_key=True, nullable=False, default=uuid32())
    rolename = Column(String(40), nullable=False)
    permission = Column(Text, default='')
    sort = Column(Integer, nullable=False, default=20)
    # 状态:( 0 禁用；1 启用, 默认1)
    status = Column(Integer, nullable=False, default=1)
    utc_created_at = Column(TIMESTAMP, default=datetimezone)

    @property
    def created_at(self):
        return utc_to_timezone(self.utc_created_at)

    @classmethod
    def option_html(cls, role_id=None):
        query = cls.session.query(Role)
        query = query.filter(Role.status == 1)
        rows = query.order_by(Role.sort.asc()).all()
        SysLogger.debug(query.statement)
        option_str = ''
        for row in rows:
            selected = 'selected' if role_id==row.uuid else ''
            option_str += '<option value="%s" %s>%s</option>' % (row.uuid, selected, row.rolename)

        # SysLogger.debug('option_str: %s' % option_str)
        return option_str

    @classmethod
    def get_permission(cls, role_id):
        query = cls.session.query('permission')
        query = query.filter(Role.uuid == role_id)
        return query.scalar()


class User(BaseModel):
    """
    user model
    """
    __tablename__ = 'sys_admin_user'

    uuid = Column(String(32), primary_key=True, nullable=False, default=uuid32())
    role_id = Column(String(32), ForeignKey('sys_admin_role.uuid'))
    password = Column(String(128), nullable=False, default='')
    username = Column(String(40), nullable=False)
    mobile = Column(String(11), nullable=True)
    email = Column(String(80), nullable=True)
    permission = Column(Text, default='')
    # 用户状态:(0 锁定, 1正常, 默认1)
    status = Column(Integer, nullable=False, default=1)
    utc_last_login_at = Column(TIMESTAMP, nullable=True)
    utc_created_at = Column(TIMESTAMP, default=datetimezone)

    @property
    def last_login_at(self):
        return utc_to_timezone(self.utc_last_login_at)

    @property
    def created_at(self):
        return utc_to_timezone(self.utc_created_at)

    @property
    def role_permission(self):
        query = "select permission from sys_admin_role where uuid='%s'" % self.role_id
        permission = User.session.execute(query).scalar()
        try:
            return json.loads(permission)
        except Exception as e:
            raise e
        return []

    @classmethod
    def get_permission(cls):
        try:
            return json.loads(cls.permission)
        except Exception as e:
            raise e
        return []


class AdminMenu(BaseModel):
    """
    user group map model
    """
    __tablename__ = 'sys_admin_menu'

    uuid = Column(String(32), primary_key=True, nullable=False, default=uuid32())
    user_id = Column(String(32), ForeignKey('sys_admin_user.uuid'), nullable=False)
    parent_id = Column(String(32), nullable=False)
    code = Column(String(64), nullable=True)
    title = Column(String(20), nullable=False)
    icon = Column(String(20), nullable=False)
    path = Column(String(200), nullable=False)
    param = Column(String(200), nullable=False)
    target = Column(String(20), nullable=False)
    nav = Column(Integer, nullable=False)
    sort = Column(Integer, nullable=False)
    status = Column(Integer, nullable=False)
    utc_created_at = Column(TIMESTAMP, default=datetimezone)


    @property
    def created_at(self):
        return utc_to_timezone(self.utc_created_at)

    @classmethod
    def info(cls, uuid=None, path=None):
        """获取当前访问节点信息

        [description]

        Keyword Arguments:
            uuid {str} -- [description] (default: {''})

        Returns:
            [type] -- [description]
        """
        query = cls.session.query(AdminMenu)
        if uuid:
            query = query.filter(AdminMenu.uuid == uuid)
        if path:
            path = path.split('?')[0]
            if path[-1:]=='/':
                path = path[0:-1]
            if path[-5:]=='.html':
                path = path[0:-5]

            query = query.filter(AdminMenu.path == path)

        row = query.first()
        row = row.as_dict() if row else None
        # SysLogger.debug(query.statement)

        return row

    @classmethod
    def brand_crumbs(cls, uuid):
        """获取当前节点的面包屑

        [description]

        Arguments:
            uuid {[type]} -- [description]

        Returns:
            [type] -- [description]
        """
        menu = []
        row = cls.info(uuid=uuid)
        if row['parent_id']!='' and row['parent_id']!='0':
            menu.append(row)
            child = cls.brand_crumbs(row['parent_id'])
            if len(child):
                menu.extend(child)
        return menu


    @classmethod
    def main_menu(cls, parent_id='0', level=0):
        """获取后台主菜单(一级 > 二级 > 三级)
            后台顶部和左侧使用

            Keyword Arguments:
                parent_id {str} -- 父ID (default: {'0'})
                level {number} -- 层级数 (default: {0})
            Returns:
                [type] -- [description]
        """
        trees = []
        if not len(trees):
            filds = ['uuid', 'code', 'parent_id', 'title', 'path', 'param', 'target', 'icon']
            query = cls.session.query(AdminMenu)
            query = query.filter(AdminMenu.status == 1)
            query = query.filter(AdminMenu.nav == 1)
            rows = query.order_by(AdminMenu.sort.asc()).all()
            # print('query.statement: ', query.statement)
            for row in rows:
                row = row.as_dict(filds)
                if row.get('parent_id')!=parent_id:
                    continue

                if level==3:
                    return trees

                # 过滤没访问权限的节点
                # if (!RoleModel::checkAuth($v['id'])) {
                #     unset($data[$k]);
                #     continue;
                # }
                row['children'] = cls.main_menu(row.get('uuid'), level+1)
                trees.append(row)

        return trees


    @staticmethod
    def children(parent_id='0', status=None, level=0):
        """获取指定节点下的所有子节点(不含快捷收藏的菜单)
        """
        trees = []
        if not len(trees):
            filds = ['uuid', 'code', 'parent_id', 'title', 'path', 'param', 'target', 'icon', 'sort', 'status']
            query = AdminMenu.session.query(AdminMenu)
            query = query.filter(AdminMenu.user_id == '0')
            query = query.filter(AdminMenu.parent_id == parent_id)
            if status in [1,0]:
                query = query.filter(AdminMenu.status == status)
            rows = query.order_by(AdminMenu.sort.asc()).all()
            data = []
            for row in rows:
                if level==3:
                    return trees
                row = row.as_dict(filds)

                # 过滤没访问权限的节点
                # if (!RoleModel::checkAuth($v['id'])) {
                #     unset($data[$k]);
                #     continue;
                # }
                row['children'] = AdminMenu.children(row.get('uuid'), status, level+1)
                trees.append(row)

        return trees

