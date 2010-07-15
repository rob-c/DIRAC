########################################################################
# $HeadURL$
########################################################################
""" ProxyRepository class is a front-end to the proxy repository Database
"""

__RCSID__ = "$Id$"

import time
try:
  import hashlib as md5
except:
  import md5
from DIRAC  import gConfig, gLogger, S_OK, S_ERROR
from DIRAC.Core.Utilities import Time
from DIRAC.Core.Base.DB import DB

class UserProfileDB( DB ):

  def __init__( self ):
    DB.__init__( self, 'UserProfileDB', 'Framework/UserProfileDB', 10 )
    retVal = self.__initializeDB()
    if not retVal[ 'OK' ]:
      raise Exception( "Can't create tables: %s" % retVal[ 'Message' ] )

  def __initializeDB( self ):
    """
    Create the tables
    """
    self.__permValues = [ 'USER', 'GROUP', 'VO', 'ALL' ]
    self.__permAttrs = [ 'ReadAccess', 'PublishAccess' ]
    retVal = self._query( "show tables" )
    if not retVal[ 'OK' ]:
      return retVal

    tablesInDB = [ t[0] for t in retVal[ 'Value' ] ]
    tablesD = {}

    if 'up_Users' not in tablesInDB:
      tablesD[ 'up_Users' ] = { 'Fields' : { 'Id' : 'INTEGER AUTO_INCREMENT NOT NULL',
                                             'UserName' : 'VARCHAR(32) NOT NULL',
                                             'LastAccess' : 'DATETIME'
                                            },
                                        'PrimaryKey' : 'Id',
                                        'UniqueIndexes' : { 'U' : [ 'UserName' ] }
                                      }

    if 'up_Groups' not in tablesInDB:
      tablesD[ 'up_Groups' ] = { 'Fields' : { 'Id' : 'INTEGER AUTO_INCREMENT NOT NULL',
                                              'UserGroup' : 'VARCHAR(32) NOT NULL',
                                              'LastAccess' : 'DATETIME'
                                            },
                                        'PrimaryKey' : 'Id',
                                        'UniqueIndexes' : { 'G' : [ 'UserGroup' ] }
                                      }

    if 'up_ProfilesData' not in tablesInDB:
      tablesD[ 'up_ProfilesData' ] = { 'Fields' : { 'UserId' : 'INTEGER',
                                                    'GroupId' : 'INTEGER',
                                                    'Profile' : 'VARCHAR(255) NOT NULL',
                                                    'VarName' : 'VARCHAR(255) NOT NULL',
                                                    'Data' : 'BLOB',
                                                    'ReadAccess' : 'VARCHAR(10) DEFAULT "USER"',
                                                    'PublishAccess' : 'VARCHAR(10) DEFAULT "USER"'
                                                  },
                                      'PrimaryKey' : [ 'UserId', 'GroupId', 'Profile', 'VarName' ],
                                      'Indexes' : { 'ProfileKey' : [ 'UserId', 'GroupId', 'Profile' ],
                                                    'UserKey' : [ 'UserId' ] }
                                     }

    if 'up_HashTags' not in tablesInDB:
      tablesD[ 'up_HashTags' ] = { 'Fields' : { 'UserId' : 'INTEGER',
                                                'GroupId' : 'INTEGER',
                                                'HashTag' : 'VARCHAR(32) NOT NULL',
                                                'TagName' : 'VARCHAR(255) NOT NULL',
                                                'LastAccess' : 'DATETIME'
                                              },
                                    'PrimaryKey' : [ 'UserId', 'GroupId', 'TagName' ],
                                    'Indexes' : { 'HashKey' : [ 'UserId', 'HashTag' ] }
                                  }
    return self._createTables( tablesD )

  def __getUserId( self, userName, insertIfMissing = True, connObj = False ):
    result = self._escapeString( userName )
    if not result[ 'OK' ]:
      return result
    sqlUserName = result[ 'Value' ]
    selectSQL = "SELECT Id FROM `up_Users` WHERE UserName = %s" % sqlUserName
    result = self._query( selectSQL, connObj )
    if not result[ 'OK' ]:
      return result
    data = result[ 'Value' ]
    if len( data ) > 0:
      id = data[0][0]
      self._update ( "UPDATE `up_Users` SET LastAccess = UTC_TIMESTAMP() WHERE Id = %s" % id )
      return S_OK( id )
    if not insertIfMissing:
      return S_ERROR( "No user %s defined in the DB" % userName )
    insertSQL = "INSERT INTO `up_Users` ( Id, UserName, LastAccess ) VALUES ( 0, %s, UTC_TIMESTAMP() )" % sqlUserName
    result = self._update( insertSQL, connObj )
    if not result[ 'OK' ]:
      return result
    return S_OK( result[ 'lastRowId' ] )

  def __getGroupId( self, groupName, insertIfMissing = True, connObj = False ):
    result = self._escapeString( groupName )
    if not result[ 'OK' ]:
      return result
    sqlGroupName = result[ 'Value' ]
    selectSQL = "SELECT Id FROM `up_Groups` WHERE UserGroup = %s" % sqlGroupName
    result = self._query( selectSQL, connObj )
    if not result[ 'OK' ]:
      return result
    data = result[ 'Value' ]
    if len( data ) > 0:
      id = data[0][0]
      self._update ( "UPDATE `up_Groups` SET LastAccess = UTC_TIMESTAMP() WHERE Id = %s" % id )
      return S_OK( id )
    if not insertIfMissing:
      return S_ERROR( "No group %s defined in the DB" % groupName )
    insertSQL = "INSERT INTO `up_Groups` ( Id, UserGroup, LastAccess ) VALUES ( 0, %s, UTC_TIMESTAMP() )" % sqlGroupName
    result = self._update( insertSQL, connObj )
    if not result[ 'OK' ]:
      return result
    return S_OK( result[ 'lastRowId' ] )

  def getUserGroupIds( self, userName, userGroup, insertIfMissing = True, connObj = False ):
    result = self.__getUserId( userName, insertIfMissing, connObj = connObj )
    if not result[ 'OK' ]:
      return result
    userId = result[ 'Value' ]
    result = self.__getGroupId( userGroup, insertIfMissing, connObj = connObj )
    if not result[ 'OK' ]:
      return result
    groupId = result[ 'Value' ]
    return S_OK( ( userId, groupId ) )

  def deleteUserProfile( self, userName, userGroup = False ):
    """
    Delete the profiles for a user
    """
    result = self.__getUserId( userName )
    if not result[ 'OK' ]:
      return result
    userId = result[ 'Value' ]
    sqlCond = [ 'UserId=%s' % userId ]
    if userGroup:
      result = self.__getGroupId( userGroup )
      if not result[ 'OK' ]:
        return result
      groupId = result[ 'Value' ]
      sqlCond.append( "GroupId=%s" % userGroup )
    delSQL = "DELETE FROM `up_ProfilesData` WHERE %s" % " AND ".join( sqlCond )
    result = self._update( delSQL )
    if not result[ 'OK' ] or not userGroup:
      return result
    delSQL = "DELETE FROM `up_Users` WHERE Id = %s" % userId
    return self._update( delSQL )

  def __webProfileUserDataCond( self, userIds, sqlProfileName, sqlVarName = False ):
    condSQL = [ '`up_ProfilesData`.UserId=%s' % userIds[0],
                '`up_ProfilesData`.GroupId=%s' % userIds[1],
                '`up_ProfilesData`.Profile=%s' % sqlProfileName ]
    if sqlVarName:
      condSQL.append( '`up_ProfilesData`.VarName=%s' % sqlVarName )
    return " AND ".join( condSQL )

  def __webProfileReadAccessDataCond( self, userIds, ownerIds, sqlProfileName, sqlVarName = False ):
    permCondSQL = []
    permCondSQL.append( '`up_ProfilesData`.UserId = %s AND `up_ProfilesData`.GroupId = %s' % ownerIds )
    permCondSQL.append( '`up_ProfilesData`.GroupId=%s AND `up_ProfilesData`.ReadAccess="GROUP"' % userIds[1] )
    permCondSQL.append( '`up_ProfilesData`.ReadAccess="ALL"' )
    sqlCond = []
    sqlCond.append( '`up_ProfilesData`.Profile = %s' % sqlProfileName )
    if sqlVarName:
      sqlCond.append( "`up_ProfilesData`.VarName = %s" % ( sqlVarName ) )
    #Perms
    sqlCond.append( "( ( %s ) )" % " ) OR ( ".join( permCondSQL ) )
    return " AND ".join( sqlCond )

  def __webProfilePublishAccessDataCond( self, userIds, sqlProfileName ):
    condSQL = []
    condSQL.append( '`up_ProfilesData`.UserId = %s AND `up_ProfilesData`.GroupId=%s' % userIds )
    condSQL.append( '`up_ProfilesData`.GroupId=%s AND `up_ProfilesData`.PublishAccess="GROUP"' % userIds[1] )
    condSQL.append( '`up_ProfilesData`.PublishAccess="ALL"' )
    sqlCond = "`up_ProfilesData`.Profile = %s AND ( ( %s ) )" % ( sqlProfileName,
                                                                  " ) OR ( ".join( condSQL ) )
    return sqlCond

  def __parsePerms( self, perms, addMissing = True ):
    normPerms = {}
    for pName in self.__permAttrs:
      if pName not in perms:
        if addMissing:
          normPerms[ pName ] = self.__permValues[0]
        continue
      else:
        permVal = perms[ pName ].upper()
        for nV in self.__permValues:
          if nV == permVal:
            normPerms[ pName ] = nV
            break
        if pName not in normPerms and addMissing:
          normPerms[ pName ] = self.__permValues[0]

    if 'PublishAccess' in normPerms:
      if 'ReadAccess' in normPerms:
        iP = self.__permValues.index( normPerms[ 'PublishAccess' ] )
        iR = self.__permValues.index( normPerms[ 'ReadAccess' ] )
        if iP > iR:
          normPerms[ 'ReadAccess' ] = self.__permValues[ iP ]
    return normPerms

  def retrieveVarById( self, userIds, ownerIds, profileName, varName, connObj = False ):
    """
    Get a data entry for a profile
    """
    result = self._escapeString( profileName )
    if not result[ 'OK' ]:
      return result
    sqlProfileName = result[ 'Value' ]

    result = self._escapeString( varName )
    if not result[ 'OK' ]:
      return result
    sqlVarName = result[ 'Value' ]

    selectSQL = "SELECT data FROM `up_ProfilesData` WHERE %s" % self.__webProfileReadAccessDataCond( userIds, ownerIds,
                                                                                                     sqlProfileName, sqlVarName )
    result = self._query( selectSQL, conn = connObj )
    if not result[ 'OK' ]:
      return result
    data = result[ 'Value' ]
    if len( data ) > 0:
      return S_OK( data[0][0] )
    return S_ERROR( "No data for userIds %s profileName %s varName %s" % ( userIds, profileName, varName ) )

  def retrieveAllUserVarsById( self, userIds, profileName, connObj = False ):
    """
    Get a data entry for a profile
    """
    result = self._escapeString( profileName )
    if not result[ 'OK' ]:
      return result
    sqlProfileName = result[ 'Value' ]

    selectSQL = "SELECT varName, data FROM `up_ProfilesData` WHERE %s" % self.__webProfileUserDataCond( userIds, sqlProfileName )
    result = self._query( selectSQL, conn = connObj )
    if not result[ 'OK' ]:
      return result
    data = result[ 'Value' ]
    return S_OK( dict( data ) )

  def retrieveVarPermsById( self, userIds, ownerIds, profileName, varName, connObj = False ):
    """
    Get a data entry for a profile
    """
    result = self._escapeString( profileName )
    if not result[ 'OK' ]:
      return result
    sqlProfileName = result[ 'Value' ]

    result = self._escapeString( varName )
    if not result[ 'OK' ]:
      return result
    sqlVarName = result[ 'Value' ]

    selectSQL = "SELECT %s FROM `up_ProfilesData` WHERE %s" % ( ", ".join( self.__permAttrs ),
                                                                self.__webProfileReadAccessDataCond( userIds, ownerIds,
                                                                                                     sqlProfileName, sqlVarName )
                                                              )
    result = self._query( selectSQL, conn = connObj )
    if not result[ 'OK' ]:
      return result
    data = result[ 'Value' ]
    if len( data ) > 0:
      permDict = {}
      for i in range( len( self.__permAttrs ) ):
        permDict[ self.__permAttrs[ i ] ] = data[0][i]
      return S_OK( permDict )
    return S_ERROR( "No data for userIds %s profileName %s varName %s" % ( userIds, profileName, varName ) )

  def deleteVarByUserId( self, userIds, profileName, varName, connObj = False ):
    """
    Remove a data entry for a profile
    """
    result = self._escapeString( profileName )
    if not result[ 'OK' ]:
      return result
    sqlProfileName = result[ 'Value' ]

    result = self._escapeString( varName )
    if not result[ 'OK' ]:
      return result
    sqlVarName = result[ 'Value' ]

    selectSQL = "DELETE FROM `up_ProfilesData` WHERE %s" % self.__webProfileUserDataCond( userIds, sqlProfileName, sqlVarName )
    return self._update( selectSQL, conn = connObj )

  def storeVarByUserId( self, userIds, profileName, varName, data, perms, connObj = False ):
    """
    Set a data entry for a profile
    """
    sqlInsertValues = []
    sqlInsertKeys = []

    sqlInsertKeys.append( ( 'UserId', userIds[0] ) )
    sqlInsertKeys.append( ( 'GroupId', userIds[1] ) )

    result = self._escapeString( profileName )
    if not result[ 'OK' ]:
      return result
    sqlProfileName = result[ 'Value' ]
    sqlInsertKeys.append( ( 'Profile', sqlProfileName ) )

    result = self._escapeString( varName )
    if not result[ 'OK' ]:
      return result
    sqlVarName = result[ 'Value' ]
    sqlInsertKeys.append( ( 'VarName', sqlVarName ) )

    result = self._escapeString( data )
    if not result[ 'OK' ]:
      return result
    sqlInsertValues.append( ( 'Data', result[ 'Value' ] ) )

    normPerms = self.__parsePerms( perms )
    for k in normPerms:
      sqlInsertValues.append( ( k, '"%s"' % normPerms[ k ] ) )

    sqlInsert = sqlInsertKeys + sqlInsertValues
    insertSQL = "INSERT INTO `up_ProfilesData` ( %s ) VALUES ( %s )" % ( ", ".join( [ f[0] for f in sqlInsert ] ),
                                                                         ", ".join( [ str( f[1] ) for f in sqlInsert ] ) )
    result = self._update( insertSQL, conn = connObj )
    if result[ 'OK' ]:
      return result
    #If error and not duplicate -> real error
    if result[ 'Message' ].find( "Duplicate entry" ) == -1:
      return result
    updateSQL = "UPDATE `up_ProfilesData` SET %s WHERE %s" % ( ", ".join( [ "%s=%s" % f for f in sqlInsertValues ] ),
                                                               self.__webProfileUserDataCond( userIds,
                                                                                              sqlProfileName,
                                                                                              sqlVarName ) )
    return self._update( updateSQL, conn = connObj )

  def setUserVarPermsById( self, userIds, profileName, varName, perms ):

    result = self._escapeString( profileName )
    if not result[ 'OK' ]:
      return result
    sqlProfileName = result[ 'Value' ]

    result = self._escapeString( varName )
    if not result[ 'OK' ]:
      return result
    sqlVarName = result[ 'Value' ]

    nPerms = self.__parsePerms( perms, False )
    if not nPerms:
      return S_OK()
    sqlPerms = ",".join( [ "%s='%s'" % ( k, nPerms[k] ) for k in nPerms ] )

    updateSql = "UPDATE `up_ProfilesData` SET %s WHERE %s" % ( sqlPerms,
                                                               self.__webProfileUserDataCond( userIds,
                                                                                              sqlProfileName,
                                                                                              sqlVarName ) )
    return self._update( updateSql )

  def retrieveVar( self, userName, userGroup, ownerName, ownerGroup, profileName, varName, connObj = False ):
    """
    Get a data entry for a profile
    """
    result = self.getUserGroupIds( userName, userGroup )
    if not result[ 'OK' ]:
      return result
    userIds = result[ 'Value' ]

    result = self.getUserGroupIds( ownerName, ownerGroup )
    if not result[ 'OK' ]:
      return result
    ownerIds = result[ 'Value' ]

    return self.retrieveVarById( userIds, ownerIds, profileName, varName, connObj )

  def retrieveAllUserVars( self, userName, userGroup, profileName, connObj = False ):
    """
    Helper for getting data
    """
    result = self.getUserGroupIds( userName, userGroup )
    if not result[ 'OK' ]:
      return result
    userIds = result[ 'Value' ]
    return self.retrieveAllUserVarsById( userIds, profileName, connObj )

  def retrieveVarPerms( self, userName, userGroup, ownerName, ownerGroup, profileName, varName, connObj = False ):
    result = self.getUserGroupIds( userName, userGroup )
    if not result[ 'OK' ]:
      return result
    userIds = result[ 'Value' ]

    result = self.getUserGroupIds( ownerName, ownerGroup, False )
    if not result[ 'OK' ]:
      return result
    ownerIds = result[ 'Value' ]

    return self.retrieveVarPermsById( userIds, ownerIds, profileName, varName, connObj )

  def setUserVarPerms( self, userName, userGroup, profileName, varName, perms ):
    result = self.getUserGroupIds( userName, userGroup )
    if not result[ 'OK' ]:
      return result
    userIds = result[ 'Value' ]
    return self.setUserVarPermsById( userIds, profileName, varName, perms )

  def storeVar( self, userName, userGroup, profileName, varName, data, perms = {} ):
    """
    Helper for setting data
    """
    result = self._getConnection()
    if not result[ 'OK' ]:
      return result
    connObj = result[ 'Value' ]
    try:
      result = self.getUserGroupIds( userName, userGroup )
      if not result[ 'OK' ]:
        return result
      userIds = result[ 'Value' ]
      return self.storeVarByUserId( userIds, profileName, varName, data, perms = perms, connObj = connObj )
    finally:
      connObj.close()

  def deleteVar( self, userName, userGroup, profileName, varName ):
    """
    Helper for deleteting data
    """
    result = self._getConnection()
    if not result[ 'OK' ]:
      return result
    connObj = result[ 'Value' ]
    try:
      result = self.getUserGroupIds( userName, userGroup, connObj = connObj )
      if not result[ 'OK' ]:
        return result
      userIds = result[ 'Value' ]
      return self.deleteVarByUserId( userIds, profileName, varName, connObj = connObj )
    finally:
      connObj.close()

  def listVarsById( self, userIds, profileName, filterDict = {} ):
    result = self._escapeString( profileName )
    if not result[ 'OK' ]:
      return result
    sqlProfileName = result[ 'Value' ]
    sqlCond = [ "`up_Users`.Id = `up_ProfilesData`.UserId",
                "`up_Groups`.Id = `up_ProfilesData`.GroupId",
                self.__webProfilePublishAccessDataCond( userIds, sqlProfileName ) ]
    if filterDict:
      if 'UserGroup' in filterDict:
        groups = filterDict[ 'UserGroup' ]
        if type( groups ) in ( types.StringType, types.UnicodeType ):
          groups = [ groups ]
        groupIds = [ userIds[1] ]
        for group in groups:
          result = self.__getGroupId( group )
          if not result[ 'OK' ]:
            return result
          groupIds.append( group )
        sqlCond.append( "`up_ProfilesData`.GroupId in ( %s )" % ", ".join( [ str( groupId ) for groupId in groupIds ] ) )
    sqlVars2Get = [ "`up_Users`.UserName", "`up_Groups`.UserGroup", "`up_ProfilesData`.VarName" ]
    sqlQuery = "SELECT %s FROM `up_Users`, `up_Groups`, `up_ProfilesData` WHERE %s" % ( ", ".join( sqlVars2Get ),
                                                                                        " AND ".join( sqlCond ) )

    return self._query( sqlQuery )

  def listVars( self, userName, userGroup, profileName, filterDict = {} ):
    result = self.getUserGroupIds( userName, userGroup )
    if not result[ 'OK' ]:
      return result
    userIds = result[ 'Value' ]
    return self.listVarsById( userIds, profileName, filterDict )

  def storeHashTagById( self, userIds, tagName, hashTag = False, connObj = False ):
    """
    Set a data entry for a profile
    """
    if not hashTag:
      hashTag = md5.md5()
      hashTag.update( "%s;%s;%s" % ( Time.dateTime(), userIds, tagName ) )
      hashTag = hashTag.hexdigest()
    hashTagUnescaped = hashTag
    result = self._escapeString( hashTag )
    if not result[ 'OK' ]:
      return result
    hashTag = result[ 'Value' ]
    result = self._escapeString( tagName )
    if not result[ 'OK' ]:
      return result
    tagName = result[ 'Value' ]
    insertSQL = "INSERT INTO `up_HashTags` ( UserId, GroupId, TagName, HashTag ) VALUES ( %s, %s, %s, %s )" % ( userIds[0], userIds[1], tagName, hashTag )
    result = self._update( insertSQL, conn = connObj )
    if result[ 'OK' ]:
      return S_OK( hashTagUnescaped )
    #If error and not duplicate -> real error
    if result[ 'Message' ].find( "Duplicate entry" ) == -1:
      return result
    updateSQL = "UPDATE `up_HashTags` set HashTag=%s WHERE UserId = %s AND GroupId = %s AND TagName = %s" % ( hashTag, userIds[0], userIds[1], tagName )
    result = self._update( updateSQL, conn = connObj )
    if not result[ 'OK' ]:
      return result
    return S_OK( hashTagUnescaped )

  def retrieveHashTagById( self, userIds, hashTag, connObj = False ):
    """
    Get a data entry for a profile
    """
    result = self._escapeString( hashTag )
    if not result[ 'OK' ]:
      return result
    hashTag = result[ 'Value' ]
    selectSQL = "SELECT TagName FROM `up_HashTags` WHERE UserId = %s AND GroupId = %s AND HashTag = %s" % ( userIds[0], userIds[1], hashTag )
    result = self._query( selectSQL, conn = connObj )
    if not result[ 'OK' ]:
      return result
    data = result[ 'Value' ]
    if len( data ) > 0:
      return S_OK( data[0][0] )
    return S_ERROR( "No data for combo userId %s hashTag %s" % ( userIds, hashTag ) )

  def retrieveAllHashTagsById( self, userIds, connObj = False ):
    """
    Get a data entry for a profile
    """
    selectSQL = "SELECT HashTag, TagName FROM `up_HashTags` WHERE UserId = %s AND GroupId = %s" % ( userIds[0], userIds[1] )
    result = self._query( selectSQL, conn = connObj )
    if not result[ 'OK' ]:
      return result
    data = result[ 'Value' ]
    return S_OK( dict( data ) )

  def storeHashTag( self, userName, userGroup, tagName, hashTag = False ):
    """
    Helper for deleteting data
    """
    result = self._getConnection()
    if not result[ 'OK' ]:
      return result
    connObj = result[ 'Value' ]
    try:
      result = self.getUserGroupIds( userName, userGroup, connObj = connObj )
      if not result[ 'OK' ]:
        return result
      userIds = result[ 'Value' ]
      return self.storeHashTagById( userIds, tagName, hashTag, connObj = connObj )
    finally:
      connObj.close()

  def retrieveHashTag( self, userName, userGroup, hashTag ):
    """
    Helper for deleteting data
    """
    result = self._getConnection()
    if not result[ 'OK' ]:
      return result
    connObj = result[ 'Value' ]
    try:
      result = self.getUserGroupIds( userName, userGroup, connObj = connObj )
      if not result[ 'OK' ]:
        return result
      userIds = result[ 'Value' ]
      return self.retrieveHashTagById( userIds, hashTag, connObj = connObj )
    finally:
      connObj.close()

  def retrieveAllHashTags( self, userName, userGroup ):
    """
    Helper for deleteting data
    """
    result = self._getConnection()
    if not result[ 'OK' ]:
      return result
    connObj = result[ 'Value' ]
    try:
      result = self.getUserGroupIds( userName, userGroup, connObj = connObj )
      if not result[ 'OK' ]:
        return result
      userIds = result[ 'Value' ]
      return self.retrieveAllHashTagsById( userIds, connObj = connObj )
    finally:
      connObj.close()
