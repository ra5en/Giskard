# -*- coding: utf-8 -*-
# This file is part of Giskard.
#
# Copyright(c) 2010-2011 Simone Margaritelli
# evilsocket@gmail.com
# http://www.evilsocket.net
# http://www.backbox.org
#
# This file may be licensed under the terms of of the
# GNU General Public License Version 2 (the ``GPL'').
#
# Software distributed under the License is distributed
# on an ``AS IS'' basis, WITHOUT WARRANTY OF ANY KIND, either
# express or implied. See the GPL for the specific language
# governing rights and limitations.
#
# You should have received a copy of the GPL along with this
# program. If not, go to http://www.gnu.org/licenses/gpl.html
# or write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
from core.Configuration import Config
from core.Daemon        import Daemon
from core.Log           import Log
from core.NetworkParser import NetworkParser

import os 
import time
import threading

class TriggerUndoScheduler( threading.Thread ):
  def __init__( self, address, undo, timeout, daemon ):
    threading.Thread.__init__(self)
    self.address = address
    self.undo    = undo
    self.timeout = timeout
    self.daemon  = daemon

  def run(self):
    try:
      time.sleep( self.timeout )
      self.daemon.log( "Undoing trigger for address %s" % NetworkParser.long2address( self.address ) )
      os.system( self.undo )
    except Exception as e:
      self.daemon.error( e )
    finally:
      self.daemon.removeTrigger( self.address )
                 
class Giskard(Daemon):
  def __init__( self, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null' ):
    Daemon.__init__( self, Config.getInstance().pidfile, stdin, stdout, stderr )

    self.config   = Config.getInstance()
    self.netstat  = NetworkParser()
    self.triggers = []
    self.lock     = threading.Lock()
    self.log_lock = threading.Lock()

  def start(self):
    Log.info( "Giskard daemon started." )
    Daemon.start( self )

  def stop(self):
    Log.info( "Giskard daemon stopped." )
    Daemon.stop( self )

  def log( self, message ):
    self.log_lock.acquire()
    Log.info( message )
    self.log_lock.release()

  def error( self, message ):
    self.log_lock.acquire()
    Log.error( message )
    self.log_lock.release()
    
  def removeTrigger( self, address ):
    self.lock.acquire()
    self.triggers.remove(address)
    self.lock.release()

  def addTrigger( self, address, trigger, undo, timeout ):
    try:
      os.system( trigger )
      self.lock.acquire()
      self.triggers.append(address)

      if undo is not None:
        TriggerUndoScheduler( address, undo, timeout, self ).start()
      
    except Exception as e:
      Log.error( e )
    finally:
      self.lock.release()
  
  def run(self):
    Log.info( "Giskard is now running ." )
    
    while True:
      self.netstat.run()

      for address, hits in self.netstat.load.iteritems():
        for port, nhits in hits.iteritems():
          rule = self.config.rules[ port ]
          # if exceeded the threshold and still doesn't have an active trigger
          if nhits > rule.threshold and address not in self.triggers:
            saddress = self.netstat.long2address(address)
            trigger  = rule.rule % saddress
            undo     = rule.undo % saddress if rule.undo is not None else None

            Log.warning( "Address %s has exceeded the threshold of %d concurrent requests on port %d with %d hits, triggering rule '%s' for %d seconds." % (
              saddress,
              rule.threshold,
              port,
              nhits,
              trigger,
              rule.timeout
            ))

            self.addTrigger( address, trigger, undo, rule.timeout )
      
      time.sleep( self.config.sleep )