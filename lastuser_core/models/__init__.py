# -*- coding: utf-8 -*-

from coaster.sqlalchemy import TimestampMixin, BaseMixin, BaseScopedNameMixin, UuidMixin  # Imported from here by other models  # NOQA
from coaster.db import db


from .user import *          # NOQA
from .session import *       # NOQA
from .client import *        # NOQA
from .notification import *  # NOQA


def getuser(name):
    if '@' in name:
        # TODO: This should have used UserExternalId.__at_username_services__,
        # but this bit has traditionally been for Twitter only. Fix pending.
        if name.startswith('@'):
            extid = UserExternalId.get(service='twitter', username=name[1:])
            if extid and extid.user.is_active:
                return extid.user
            else:
                return None
        else:
            useremail = UserEmail.get(email=name)
            if useremail and useremail.user is not None and useremail.user.is_active:
                return useremail.user
            # No verified email id. Look for an unverified id; return first found
            results = UserEmailClaim.all(email=name)
            if results and results[0].user.is_active:
                return results[0].user
            return None
    else:
        return User.get(username=name)


def getextid(service, userid):
    return UserExternalId.get(service=service, userid=userid)


def merge_users(user1, user2):
    """
    Merge two user accounts and return the new user account.
    """
    # Always keep the older account and merge from the newer account
    if user1.created_at < user2.created_at:
        keep_user, merge_user = user1, user2
    else:
        keep_user, merge_user = user2, user1

    # 1. Inspect all tables for foreign key references to merge_user and switch to keep_user.
    for model in db.Model.__subclasses__():
        if model != User:
            # a. This is a model and it's not the User model. Does it have a migrate_user classmethod?
            if hasattr(model, 'migrate_user'):
                model.migrate_user(olduser=merge_user, newuser=keep_user)
            # b. No migrate_user? Does it have a user_id column?
            elif hasattr(model, 'user_id') and hasattr(model, 'query'):
                for row in model.query.filter_by(user_id=merge_user.id).all():
                    row.user_id = keep_user.id
    # 2. Add merge_user's uuid to olduserids. Commit session.
    db.session.add(UserOldId(id=merge_user.uuid, user=keep_user))
    # 3. Mark merge_user as merged. Commit session.
    merge_user.status = USER_STATUS.MERGED
    # 4. Release the username
    merge_user.username = None
    # 5. Commit all of this
    db.session.commit()

    # 6. Return keep_user.
    return keep_user
