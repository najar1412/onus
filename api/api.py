import sqlite3
import datetime

from flask import Flask, jsonify
from flask_restful import reqparse, abort, Api, Resource, fields, marshal_with
from flask_sqlalchemy import SQLAlchemy
from flask_httpauth import HTTPBasicAuth

from packages import convert


# Config
# init app and db
app = Flask(__name__)
conn = sqlite3.connect('example.db')

# config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///example.db'
api = Api(app, '/onus/v1')
db = SQLAlchemy(app)
auth = HTTPBasicAuth()

# database models
account_tasks = db.Table('account_tasks',
    db.Column('account_id', db.Integer, db.ForeignKey('account.id')),
    db.Column('task_id', db.Integer, db.ForeignKey('task.id'))
)

task_fulfill = db.Table('task_fulfill',
    db.Column('task_id', db.Integer, db.ForeignKey('task.id')),
    db.Column('account_id', db.Integer, db.ForeignKey('account.id'))
)

task_comment = db.Table('task_comment',
    db.Column('task_id', db.Integer, db.ForeignKey('task.id')),
    db.Column('comment_id', db.Integer, db.ForeignKey('comment.id'))
)


class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String)
    password = db.Column(db.String)
    initdate = db.Column(db.String, default=str(datetime.datetime.utcnow()))

    # relationships
    # comments
    tasks = db.relationship('Task', secondary=account_tasks,
        backref=db.backref('posted_by', lazy='dynamic'))


    def __init__(self, username, password):
        self.username = username
        self.password = password


    def __repr__(self):
        return '<Account {}>'.format(self.id)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String)
    initdate = db.Column(db.String, default=str(datetime.datetime.utcnow()))
    completed = db.Column(db.Boolean, default=False)

    # relationships
    fulfill = db.relationship('Account', secondary=task_fulfill,
        backref=db.backref('fulfilling', lazy='dynamic'))
    comments = db.relationship('Comment', secondary=task_comment,
        backref=db.backref('task', lazy='dynamic'))
    # fulfilled_by = db.Column(db.String, default=str('fulfille by data'))
    # user_checkin = db.Column(db.String, default=str('check in data'))
    # checkout = db.Column(db.String, default=str('check out data'))


    def __init__(self, title):
        self.title = title

    def __repr__(self):
        return '<Task {}>'.format(self.id)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String)
    initdate = db.Column(db.String, default=str(datetime.datetime.utcnow()))
    account = db.Column(db.Integer)

    def __init__(self, content):
        self.content = content

    def __repr__(self):
        return '<Comment {}>'.format(self.id)

    # relationship
    # task

db.create_all()

# helpers
def resp(status=None, data=None, link=None, error=None, message=None):
    """Function im using to build responses"""
    response = {
        'status': status, 'data': data, 'link': link,
        'error': error, 'message': message
    }

    remove_none = []

    for x in response:
        if response[x] == None:
            remove_none.append(x)

    for x in remove_none:
        del response[x]

    return response

# auth
# Basic HTTP auth
@auth.verify_password
def verify(username, password):
    get_account = Account.query.filter_by(username=username).first()

    if not Account.query.filter_by(username=username).first():
        return False

    else:
        if get_account.password == password:
            return True

        else:
            return False


# API resources
class Entry(Resource):
    def get(self):
        entry = {
            'name': 'onus api',
            'version': 'v1',
            'resources': ''
        }

        return entry, 200


class Accounts(Resource):
    @auth.login_required
    def get(self, id):
        raw_account = Account.query.filter_by(id=id).first()

        response = resp(status='success', data=convert.jsonify((raw_account,)))
        return response, 200


    @auth.login_required
    def put(self, id):
        parser = reqparse.RequestParser()
        parser.add_argument('tasks', type=str, help='help text')
        args = parser.parse_args()

        raw_account = Account.query.filter_by(id=id).first()

        if raw_account != None:
            if 'tasks' in args and args['tasks'] != None:
                raw_task = Task.query.filter_by(id=args['tasks']).first()

                if raw_task != None:
                    raw_account.tasks.append(raw_task)
                    db.session.commit()

                    response = resp(
                        status='success', link='/accounts/{}'.format(raw_account.id)
                        ), 201

                    return response

                else:
                    return resp(error='no such task id')

            else:
                return resp(error='must enter task id')

        else:
            return resp(error='no such account id')


    @auth.login_required
    def delete(self, id):
        raw_account = Account.query.filter_by(id=id).first()

        if auth.username() == raw_account.username:
            db.session.delete(raw_account)
            db.session.commit()

            response = resp(status='success', message='account successfully deleted')
            return response

        else:
            return resp(message='Account can only be if logged in as the same account.')


class AccountsL(Resource):
    @auth.login_required
    def get(self):
        new_accounts = Account.query.all()

        response = resp(data=convert.jsonify(new_accounts), status='success')
        return response, 200


    def post(self):
        parser = reqparse.RequestParser()

        # accepted ARGs from api
        parser.add_argument('username', type=str, help='help text')
        parser.add_argument('password', type=str, help='help text')
        args = parser.parse_args()

        #process user input
        if args['username'] != None and args['password'] != None:
            new_account = Account(username=args['username'], password=args['password'])
            db.session.add(new_account)
            db.session.commit()

            response = resp(
                data=convert.jsonify((new_account,)),
                link='/accounts/{}'.format(new_account.id),
                status='success'
            )

            return response, 201

        else:
            response = resp(error='No post data', status='failed')
            return response, 400


class Tasks(Resource):
    @auth.login_required
    def get(self, id):
        raw_task = Task.query.filter_by(id=id).first()

        if raw_task != None:

            response = resp(data=convert.jsonify((raw_task,)), status='success')
            return response, 200

        else:
            response = resp(status='failed', error='no such task id')
            return response, 400


    @auth.login_required
    def put(self, id):
        parser = reqparse.RequestParser()
        parser.add_argument('completed', type=int, help='help text')
        parser.add_argument('fulfill', type=int, help='help text')
        parser.add_argument('subscribe', type=int, help='help text')
        parser.add_argument('comment', type=str, help='help text')
        args = parser.parse_args()

        get_task = Task.query.filter_by(id=id).first()

        if get_task != None:
            if args['completed'] != None:
                if args['completed'] == 1:
                    get_task.completed = 1
                    db.session.commit()

                else:
                    get_task.completed = 0
                    db.session.commit()

                response = resp(data=convert.jsonify((get_task,)), link='/tasks/{}'.format(get_task.id))
                return response, 201

            if args['fulfill'] == 1:
                get_account = Account.query.filter_by(username=auth.username()).first()
                if get_account not in get_task.fulfill:
                    get_task.fulfill.append(get_account)
                    db.session.commit()

                    response = resp(status='success', data=convert.jsonify((get_task,)), link='/tasks/{}'.format(get_task.id))
                    return response, 201

                else:
                    return resp(message='accound id already exists in task.fulfill')

            elif args['fulfill'] == 0:
                get_account = Account.query.filter_by(username=auth.username()).first()
                if get_account in get_task.fulfill:
                    get_task.fulfill.remove(get_account)
                    db.session.commit()

                    response = resp(data=convert.jsonify((get_task,)), link='/tasks/{}'.format(get_task.id))
                    return response, 201

                else:
                    return resp(message='accound id does not exist in tasks.fulfill')

            if args['comment'] != None:
                get_account = Account.query.filter_by(username=auth.username()).first()
                get_task = Task.query.filter_by(id=id).first()

                new_comment = Comment(content=args['comment'])
                new_comment.account = int(get_account.id)

                get_task.comments.append(new_comment)

                db.session.add(new_comment)
                db.session.commit()


                return {'there is a comment': args['comment']}

            else:
                return {'Better error': 'catching here'}


        else:
            return resp(error='no such task id')


    @auth.login_required
    def delete(self, id):
        get_task = Task.query.filter_by(id=id).first()
        get_account = Account.query.filter_by(username=auth.username()).first()

        if get_task in get_account.tasks:
            db.session.delete(get_task)
            db.session.commit()

            response = resp(status='success', message='task successfully deleted')

            return response, 201

        else:
            return resp(message='task can only deleted by the account that posted it')


class TasksL(Resource):
    def get(self):
        raw_tasks = Task.query.all()

        response = resp(data=convert.jsonify(raw_tasks), status='success')
        return response, 200


    @auth.login_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('title', type=str, help='helper text')
        args = parser.parse_args()

        if args['title'] != None:
            user_account = Account.query.filter_by(username=auth.username()).first()
            new_task = Task(title=args['title'])
            new_task.posted_by.append(user_account)
            db.session.add(new_task)
            db.session.commit()

            response = resp(
                data=convert.jsonify((new_task,)),
                link='/tasks/{}'.format(new_task.id),
                status='success'
            )

            return response, 201

        else:
            response = resp(error='missing required data', message='')
            return response, 400


class Comments(Resource):
    # imp comments
    def get(self, id):
        pass

    def put(self, id):
        pass

    def delete(self, id):
        get_comment = Comment.query.filter_by(id=id).first()
        get_account = Account.query.filter_by(username=auth.username()).first()

        if get_comment.account == get_account.id:
            db.session.delete(get_comment)
            db.session.commit()

            return resp(message='comment successfully deleted')

        else:
            return resp(message='only account that posted the comment can delete it')

        return {'comment': convert.jsonify((get_comment,))}



class CommentsL(Resource):
    def get(self):
        pass

    def post(self):
        pass


# routes
api.add_resource(Entry, '/')
api.add_resource(Accounts, '/accounts/<id>')
api.add_resource(AccountsL, '/accounts')
api.add_resource(Tasks, '/tasks/<id>')
api.add_resource(TasksL, '/tasks')
api.add_resource(Comments, '/comments/<id>')


if __name__ == '__main__':
    app.run(debug=True, port=5050)
