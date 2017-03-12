#!/usr/bin/env python
#-*- encoding:utf-8 -*-

__version__ = '0.1'

import os, sys, inspect, sqlite3, hashlib
from argparse import ArgumentParser, RawTextHelpFormatter

latch_api = os.path.realpath( os.path.abspath( os.path.join( os.path.split( inspect.getfile( inspect.currentframe() ) )[ 0 ], "latch-sdk-python" ) ) )
if latch_api not in sys.path:
    sys.path.insert( 0, latch_api )
import latch

def main():
    parser = ArgumentParser( description = 'Latch Example manage Latch as second authentication factor (2FA)', formatter_class = RawTextHelpFormatter )

    parser.add_argument( '-v', '--version', action = 'version', version = __version__, help = 'Show program\'s version number and exit\n\n' )

    group = parser.add_mutually_exclusive_group()
    group.add_argument( '-c', '--configure', action = 'store_true', help = 'Configure Latch app ID and SECRET' )
    group.add_argument( '-g', '--get',       action = 'store_true', help = 'Get the status of a specified account with USER and PWD' )
    group.add_argument( '-a', '--add',       action = 'store_true', help = 'Add a new USER with PWD' )
    group.add_argument( '-r', '--remove',    action = 'store_true', help = 'Remove a USER\n\n' )

    parser.add_argument( '-u', '--user',   type = str, default='', help = 'User account' )
    parser.add_argument( '-p', '--pwd',    type = str, default='', help = 'Account password' )
    parser.add_argument( '-t', '--token',  type = str, default='', help = 'Latch token' )
    parser.add_argument( '-i', '--id',     type = str, default='', help = 'Latch app id' )
    parser.add_argument( '-s', '--secret', type = str, default='', help = 'Latch app secret' )

    args = parser.parse_args()

    if( args.configure ):
        if( args.id == '' or args.secret == '' ):
            print( __file__ + ': argument -c/--configure needs -i/--id and -s/--secret arguments' )
        elif( len( args.id ) != 20 or len( args.secret ) != 40  ):
            print( __file__ + ': invalid length in -i/--id or -s/--secret argument' )
        else:
            wrapper( 'configure', args )

    elif( args.get ):
        if( args.user == '' or args.pwd == '' ):
            print( __file__ + ': argument -g/--get needs -u/--user and -p/--pwd arguments' )
        elif( len( args.user ) > 50 or len( args.pwd ) > 50 ):
            print( __file__ + ': invalid length in -u/--user or -p/--pwd argument' )
        else:
            wrapper( 'get', args )

    elif( args.add ):
        if( args.user == '' or args.pwd == '' or args.token == '' ):
            print( __file__ + ': argument -a/--add needs -u/--user, -p/--pwd and -t/--token arguments' )
        elif( len( args.user ) > 50 or len( args.pwd ) > 50 or len( args.token ) != 6 ):
            print( __file__ + ': invalid length in -u/--user or -p/--pwd or -t/--token argument' )
        else:
            wrapper( 'add', args )

    elif( args.remove ):
        if( args.user == '' ):
            print( __file__ + ': argument -r/--remove needs -u/--user argument' )
        elif( len( args.user ) > 50 ):
            print( __file__ + ': invalid length in -u/--user or -p/--pwd argument' )
        else:
            wrapper( 'remove', args )

    else:
        parser.print_help()

    sys.exit( 8 ) #The module did nothing

def exit( status, connect ):
    connect.close()

    if( status == 'OK' ):
        print( __file__ + ': Successful login' )
        sys.exit( 0 )
    elif( status == 'REJECT' ):
        print( __file__ + ': Incorrect user / password / latch' )
        sys.exit( 1 )
    elif( status == 'FAIL' ):
        print( __file__ + ': You must configure with your application id and secret' )
        sys.exit( 2 )

def wrapper( action, args ):
    connect = sqlite3.connect( 'latch.db' ) #Path to the database

    if( action == 'configure' ):
        configure( connect, args.id, args.secret )
    elif( action == 'get' ):
        get( connect, args.user, args.pwd )
    elif( action == 'add' ):
        add( connect, args.user, args.pwd, args.token )
    elif( action == 'remove' ):
        remove( connect, args.user )

    connect.close()

def configure( connect, id, secret ):
    print( __file__ + ': configure: id(' + id + ') and secret(' + secret + ')' )

    cursor = connect.cursor()
    if( is_db_table( connect, 'users' ) ):
        for user in cursor.execute( 'SELECT username FROM users' ):
            remove( connect, user[ 0 ] )

    cursor.execute( 'DROP TABLE IF EXISTS latch' )
    cursor.execute( '''CREATE TABLE IF NOT EXISTS latch (
                            id     varchar( 20 ) not null,
                            secret varchar( 40 ) not null
                        )''' )

    cursor.execute( 'DROP TABLE IF EXISTS users' )
    cursor.execute( '''CREATE TABLE IF NOT EXISTS users (
                            username   varchar( 50 )  not null unique,
                            password   varchar( 128 ) not null,
                            account_id varchar( 64 )  not null
                        )''' )

    cursor.execute( "INSERT INTO latch VALUES ( ?, ? )", ( id, secret ) )

    connect.commit()

def add( connect, user, pwd, token ):
    print( __file__ + ': add: user(' + user + '), pwd(' + pwd + ') and token(' + token + ')' )

    response = get_api( connect ).pair( token )

    if( response.get_data() ):
        connect.cursor().execute( "INSERT INTO users VALUES ( ?, ?, ? )", ( user, get_hash( connect, pwd ), response.get_data().get( 'accountId' ) ) )
        connect.commit()
    else:
        print( __file__  + ': ' + response.get_error().get_message() )

def remove( connect, user ):
    print( __file__ + ': remove: user(' + user + ')' )

    response = get_api( connect ).unpair( get_db_user( connect, user )[ 2 ] )

    if( not response.get_error() ):
        connect.cursor().execute( 'DELETE FROM users WHERE username = ?', ( user, ) )
        connect.commit()
    else:
        print( __file__ + ': ' + response.get_error().get_message() )

def get( connect, user, pwd ):
    print( __file__ + ': get: user(' + user + ') and pwd(' + pwd + ')' )

    user = get_db_user( connect, user )

    if( user[ 1 ] == get_hash( connect, pwd ) ):
        response = get_api( connect ).status( user[ 2 ] )
        if( response.get_data() ):
            if( response.get_data().get( 'operations' ).get( get_db_latch( connect )[ 0 ] ).get( 'status' ) == 'on' ):
                exit( 'OK', connect )
            else:
                exit( 'REJECT', connect )
        else:
            print( __file__  + ': ' + response.get_error().get_message() )
    else:
        exit( 'REJECT', connect )

def get_api( connect ):
    configuration = get_db_latch( connect )
    return latch.Latch( configuration[ 0 ], configuration[ 1 ] )

def is_db_configured( connect ):
    return is_db_table( connect, 'latch' ) and is_db_table( connect, 'users' )

def is_db_table( connect, table ):
    cursor = connect.cursor()
    cursor.execute( "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", ( table, ) )
    return cursor.fetchone() != None

def get_db_latch( connect ):
    return get_db_data( connect, 'SELECT id, secret FROM latch' )

def get_db_user( connect, user ):
    return get_db_data( connect, 'SELECT username, password, account_id FROM users WHERE username = ?', ( user, ) )

def get_db_data( connect, query, vars = () ):
    cursor = connect.cursor()
    if( is_db_configured( connect ) ):
        cursor.execute( query, vars )
        data = cursor.fetchone()
        if( data != None ):
            return data
        else:
            exit( 'REJECT', connect )
    else:
        exit( 'FAIL', connect )

def get_hash( connect, pwd ):
    return hashlib.sha512( get_db_latch( connect )[ 0 ] + hashlib.sha512( pwd ).hexdigest() ).hexdigest()

if __name__ == '__main__':
    main()
