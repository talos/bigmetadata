'''
Util functions for tests
'''

import os
import luigi
from subprocess import check_output

import importlib
import inspect
import os

from time import time


EMPTY_RASTER = '0100000000000000000000F03F000000000000F0BF0000000000000000' \
        '000000000000000000000000000000000000000000000000000000000A000A00'


class FakeTask(object):

    task_id = 'fake'


def recreate_db(dbname='test'):
    if not os.environ.get('TRAVIS'):
        check_output('''
        psql -d gis -c "SELECT pg_terminate_backend(pg_stat_activity.pid)
                 FROM pg_stat_activity
                 WHERE pg_stat_activity.datname = '{dbname}'
                   AND pid <> pg_backend_pid();"
        '''.format(dbname=dbname), shell=True)
    check_output('dropdb --if-exists {dbname}'.format(dbname=dbname), shell=True)
    check_output('createdb {dbname} -E UTF8 -T template0'.format(dbname=dbname), shell=True)
    check_output('psql -d {dbname} -c "CREATE EXTENSION IF NOT EXISTS postgis"'.format(
        dbname=dbname), shell=True)
    os.environ['PGDATABASE'] = dbname


from contextlib import contextmanager
from luigi.worker import Worker
from luigi.scheduler import CentralPlannerScheduler


def setup():
    from tasks.meta import current_session, Base
    if Base.metadata.bind.url.database != 'test':
        raise Exception('Can only run tests on database "test"')
    session = current_session()
    session.rollback()
    session.execute('DROP SCHEMA IF EXISTS observatory CASCADE')
    session.execute('CREATE SCHEMA observatory')
    session.commit()
    Base.metadata.create_all()


def teardown():
    from tasks.meta import current_session, Base
    if Base.metadata.bind.url.database != 'test':
        raise Exception('Can only run tests on database "test"')
    session = current_session()
    session.rollback()
    Base.metadata.drop_all()
    session.execute('DROP SCHEMA IF EXISTS observatory CASCADE')
    session.commit()


def runtask(task, superclasses=None):
    '''
    Run deps of tasks then the task, faking session management

    superclasses is a list of classes that we will be willing to run as
    pre-reqs, other pre-reqs will be ignored.  Can be useful when testing to
    only run metadata classes, for example.
    '''
    from tasks.util import LOGGER
    if task.complete():
        return
    for dep in task.deps():
        if superclasses:
            for klass in superclasses:
                if isinstance(dep, klass):
                    runtask(dep, superclasses=superclasses)
                    assert dep.complete() is True
        else:
            runtask(dep)
            assert dep.complete() is True
    try:
        before = time()
        for klass, cb_dict in task._event_callbacks.iteritems():
            if isinstance(task, klass):
                start_callbacks = cb_dict.get('event.core.start', [])
                for scb in start_callbacks:
                    scb(task)
        task.run()
        task.on_success()
        after = time()
        LOGGER.warn('runtask timing %s: %s', task, round(after - before, 2))
    except Exception as exc:
        task.on_failure(exc)
        raise


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    from tasks.meta import current_session, session_commit, session_rollback
    try:
        yield current_session()
        session_commit(None)
    except Exception as e:
        session_rollback(None, e)
        raise


def collect_tasks(TaskClass):
    '''
    Returns a set of task classes whose parent is the passed `TaskClass`
    '''
    tasks = set()
    test_module = os.environ.get('TEST_MODULE', '').replace('.', os.path.sep)
    for dirpath, _, files in os.walk('tasks'):
        for filename in files:
            if not os.path.join(dirpath, filename).startswith(test_module):
                continue
            if filename.endswith('.py'):
                modulename = '.'.join([
                    dirpath.replace(os.path.sep, '.'),
                    filename.replace('.py', '')
                ])
                module = importlib.import_module(modulename)
                for _, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, TaskClass) and obj != TaskClass:
                        tasks.add((obj, ))
    return tasks


def cross(orig_list, b_name, b_list):
    result = []
    for orig_dict in orig_list:
        for b_val in b_list:
            new_dict = orig_dict.copy()
            new_dict[b_name] = b_val
            result.append(new_dict)
    return result


def collect_meta_wrappers():
    from tasks.util import MetaWrapper

    test_all = os.environ.get('TEST_ALL', '') != ''

    tasks = collect_tasks(MetaWrapper)
    for t, in tasks:
        outparams = [{}]
        for key, val in t.params.iteritems():
            outparams = cross(outparams, key, val)
        for params in outparams:
            yield t, params
            if not test_all:
                break
