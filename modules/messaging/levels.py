# This Python file uses the following encoding: utf-8
# -*- coding: utf-8 -*-
import logging
import math
import os
import random
import sqlite3
import xml.etree.ElementTree as ElementTree
from collections import OrderedDict
import datetime

from modules.helper.parser import self_heal
from modules.helper.system import system_message, ModuleLoadException
from modules.helper.modules import MessagingModule

log = logging.getLogger('levels')


class levels(MessagingModule):
    @staticmethod
    def create_db(db_location):
        if not os.path.exists(db_location):
            db = sqlite3.connect(db_location)
            cursor = db.cursor()
            log.info("Creating new tables for levels")
            cursor.execute('CREATE TABLE UserLevels (User, "Experience")')
            cursor.close()
            db.commit()
            db.close()

    def __init__(self, conf_folder, **kwargs):
        MessagingModule.__init__(self)

        conf_file = os.path.join(conf_folder, "levels.cfg")
        conf_dict = OrderedDict()
        conf_dict['gui_information'] = {'category': 'messaging'}
        conf_dict['config'] = OrderedDict()
        conf_dict['config']['message'] = u'{0} has leveled up, now he is {1}'
        conf_dict['config']['db'] = os.path.join('conf', u'levels.db')
        conf_dict['config']['experience'] = u'geometrical'
        conf_dict['config']['exp_for_level'] = 200
        conf_dict['config']['exp_for_message'] = 1
        conf_dict['config']['decrease_window'] = 60
        conf_gui = {'non_dynamic': ['config.*'],
                    'config': {
                        'experience': {
                            'view': 'dropdown',
                            'choices': ['static', 'geometrical', 'random']}}}
        config = self_heal(conf_file, conf_dict)

        self._conf_params = {'folder': conf_folder, 'file': conf_file,
                             'filename': ''.join(os.path.basename(conf_file).split('.')[:-1]),
                             'parser': config,
                             'config': conf_dict,
                             'gui': conf_gui}

        self.conf_folder = None
        self.experience = None
        self.exp_for_level = None
        self.exp_for_message = None
        self.filename = None
        self.levels = None
        self.special_levels = None
        self.db_location = None
        self.message = None
        self.decrease_window = None
        self.threshold_users = None

    def load_module(self, *args, **kwargs):
        main_settings = kwargs.get('main_settings')
        loaded_modules = kwargs.get('loaded_modules')
        if 'webchat' not in loaded_modules:
            raise ModuleLoadException("Unable to find webchat module that is needed for level module")

        conf_folder = self._conf_params['folder']
        conf_dict = self._conf_params['config']

        self.conf_folder = conf_folder
        self.experience = conf_dict['config'].get('experience')
        self.exp_for_level = float(conf_dict['config'].get('exp_for_level'))
        self.exp_for_message = float(conf_dict['config'].get('exp_for_message'))
        self.filename = os.path.abspath(os.path.join(loaded_modules['webchat']['style_location'], 'levels.xml'))
        self.levels = []
        self.special_levels = {}
        self.db_location = os.path.join(conf_dict['config'].get('db'))
        self.message = conf_dict['config'].get('message').decode('utf-8')
        self.decrease_window = int(conf_dict['config'].get('decrease_window'))
        self.threshold_users = {}

        # Load levels
        if not os.path.exists(self.filename):
            log.error("{0} not found, generating from template".format(self.filename))
            raise ModuleLoadException("{0} not found, generating from template".format(self.filename))

        if self.experience == 'random':
            self.db_location += '.random'
        self.create_db(self.db_location)

        tree = ElementTree.parse(os.path.join(conf_folder, self.filename))
        lvl_xml = tree.getroot()

        for level_data in lvl_xml:
            level_count = float(len(self.levels) + 1)
            if 'nick' in level_data.attrib:
                self.special_levels[level_data.attrib['nick']] = level_data.attrib
            else:
                if self.experience == 'geometrical':
                    level_exp = math.floor(self.exp_for_level * (pow(level_count, 1.8)/2.0))
                else:
                    level_exp = self.exp_for_level * level_count
                level_data.attrib['exp'] = level_exp
                self.levels.append(level_data.attrib)

    def set_level(self, user, queue):
        if user == 'System':
            return []
        db = sqlite3.connect(self.db_location)

        cursor = db.cursor()
        user_select = cursor.execute('SELECT User, Experience FROM UserLevels WHERE User = ?', [user])
        user_select = user_select.fetchall()

        experience = self.exp_for_message
        exp_to_add = self.calculate_experience(user)
        if len(user_select) == 1:
            row = user_select[0]
            experience = int(row[1]) + exp_to_add
            cursor.execute('UPDATE UserLevels SET Experience = ? WHERE User = ? ', [experience, user])
        elif len(user_select) > 1:
            log.error("Select yielded more than one User")
        else:
            cursor.execute('INSERT INTO UserLevels VALUES (?, ?)', [user, experience])
        db.commit()

        max_level = 0
        for level in self.levels:
            if level['exp'] < experience:
                max_level += 1
        if max_level >= len(self.levels):
            max_level -= 1

        if experience >= self.levels[max_level]['exp']:
            if self.experience == 'random':
                max_level = random.randint(0, len(self.levels) - 1)
                experience = self.levels[max_level]['exp'] - self.exp_for_level
                cursor.execute('UPDATE UserLevels SET Experience = ? WHERE User = ? ', [experience, user])
                db.commit()
            else:
                max_level += 1
            system_message(self.message.format(user, self.levels[max_level]['name']), queue)
        cursor.close()
        return self.levels[max_level]

    def process_message(self, message, queue, **kwargs):
        if message:
            if 'command' in message:
                return message
            if 'system_msg' not in message or not message['system_msg']:
                if 'user' in message and message['user'] in self.special_levels:
                    level_info = self.special_levels[message['user']]
                    if 's_levels' in message:
                        message['s_levels'].append(level_info)
                    else:
                        message['s_levels'] = [level_info]

                message['levels'] = self.set_level(message['user'], queue)
            return message

    def calculate_experience(self, user):
        exp_to_add = self.exp_for_message
        if user in self.threshold_users:
            multiplier = (datetime.datetime.now() - self.threshold_users[user]).seconds / float(self.decrease_window)
            exp_to_add *= multiplier if multiplier <= 1 else 1
        self.threshold_users[user] = datetime.datetime.now()
        return exp_to_add
