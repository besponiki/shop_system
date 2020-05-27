from mongoengine import *


class User(Document):
    meta = {'collection': 'web_admin_user'}

    session_id = StringField(db_field='session_id')
    time_alive = FloatField(db_field='time_alive')
    rank = IntField()
    login = StringField(db_field='login', unique=True)
    password = StringField(db_field='password')

    def get_rank_start_page(self):
        return{
            self.rank == 0: '/index',
            self.rank == 1: '/texts',
            self.rank == 2: '/users',
            self.rank == 3: '/feedbacks',
            self.rank == 4: '/adverts'
        }[True]

    def get_availible_pages(self):
        return {
            self.rank == 0: {'/index', '/languages', '/feedbacks', '/web_admins',
                             '/', '/finances', '/marketing', '/users', '/user', '/', '/shops',
                             '/texts', '/nullify_balance', '/drop_structure', '/graph', '/frequents',
                             '/comments', '/categories', '/adverts', '/fields', '/generate_logs', '/generate_test',
                             '/distribute_test', '/distribute_logs', '/currencies'},
            self.rank == 1: {'/texts', '/languages'},
            self.rank == 2: {'/users', '/categories', '/shops', '/adverts', '/fields', '/feedbacks', '/frequents',
                             '/comments'},
            self.rank == 3: {'/feedbacks', '/frequents', '/comments'},
            self.rank == 4: {'/adverts', '/fields'}
        }[True]

    def get_access(self, url):
        pages = self.get_availible_pages()
        return None if url in pages else self.get_rank_start_page()
