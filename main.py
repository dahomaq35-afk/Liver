import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

# =========================================================
# إعداد التطبيق
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "mt-character-system-secret"
)

app.permanent_session_lifetime = timedelta(days=30)

DATABASE = "mt_characters.db"

# =========================================================
# الصلاحيات
# =========================================================

PERMISSIONS = {

    "characters_view_all": "عرض جميع الشخصيات",
    "characters_view_details": "عرض تفاصيل الشخصيات",
    "characters_search": "البحث في الشخصيات",
    "characters_edit_all": "تعديل جميع الشخصيات",
    "characters_delete_all": "حذف جميع الشخصيات",
    "characters_hide": "إخفاء الشخصيات",
    "characters_show": "إظهار الشخصيات",
    "characters_transfer": "نقل ملكية الشخصيات",
    "characters_reset": "إعادة ضبط الشخصيات",

    "police_manage": "إدارة الشرطة",
    "police_view": "عرض الشرطة",
    "police_add": "إضافة للشرطة",
    "police_edit": "تعديل الشرطة",
    "police_delete": "حذف من الشرطة",
    "police_assign_rank": "تعيين رتبة شرطة",
    "police_change_rank": "تغيير رتبة الشرطة",
    "police_remove": "إزالة من الشرطة",

    "justice_manage": "إدارة وزارة العدل",
    "justice_view": "عرض وزارة العدل",
    "justice_add": "إضافة لوزارة العدل",
    "justice_edit": "تعديل وزارة العدل",
    "justice_delete": "حذف من وزارة العدل",
    "justice_assign_rank": "تعيين رتبة عدل",
    "justice_change_rank": "تغيير رتبة العدل",
    "justice_remove": "إزالة من وزارة العدل",

    "health_manage": "إدارة الصحة",
    "health_view": "عرض الصحة",
    "health_add": "إضافة للصحة",
    "health_edit": "تعديل الصحة",
    "health_delete": "حذف من الصحة",
    "health_assign_rank": "تعيين رتبة صحة",
    "health_change_rank": "تغيير رتبة الصحة",
    "health_remove": "إزالة من الصحة",

    "gangs_manage": "إدارة العصابات",
    "gangs_view": "عرض العصابات",
    "gangs_add": "إضافة عصابات",
    "gangs_edit": "تعديل العصابات",
    "gangs_delete": "حذف العصابات",
    "gangs_add_members": "إضافة أعضاء للعصابات",
    "gangs_remove_members": "إزالة أعضاء العصابات",
    "gangs_change_leader": "تغيير رتبة/قائد العصابة",

    "users_view": "عرض المستخدمين",
    "users_edit": "تعديل المستخدمين",
    "users_ban": "حظر المستخدمين",
    "users_unban": "فك حظر المستخدمين",
    "users_delete": "حذف المستخدمين",
    "users_disable": "تعطيل المستخدمين",
    "users_enable": "تفعيل المستخدمين",

    "permissions_view": "عرض الصلاحيات",
    "permissions_give": "إعطاء الصلاحيات",
    "permissions_remove": "إزالة الصلاحيات",
    "permissions_edit": "تعديل الصلاحيات",

    "site_settings": "إعدادات الموقع",
    "site_sections": "إدارة أقسام الموقع",
    "site_home": "إدارة الصفحة الرئيسية",
    "site_maintenance": "وضع الصيانة",

    "logs_view": "عرض السجلات",
    "logs_search": "البحث في السجلات",
    "logs_export": "تصدير السجلات",

    "admins_manage": "إدارة المدراء",
    "admins_add": "إضافة رتبة إدارية",
    "admins_remove": "إزالة رتبة إدارية",
    "admins_all_permissions": "جميع الصلاحيات",
    "admins_all_sections": "جميع الأقسام"
}

# =========================================================
# الرتب الأساسية
# =========================================================

ROLES = {

    "owner": {
        "name": "Owner",
        "permissions": set(PERMISSIONS.keys())
    },

    "co_owner": {
        "name": "Co Owner",
        "permissions": {
            "characters_view_all",
            "characters_view_details",
            "characters_edit_all",
            "characters_delete_all",
            "characters_hide",
            "characters_show",

            "police_manage",
            "police_view",
            "police_add",
            "police_edit",
            "police_delete",
            "police_assign_rank",
            "police_change_rank",
            "police_remove",

            "justice_manage",
            "justice_view",
            "justice_add",
            "justice_edit",
            "justice_delete",
            "justice_assign_rank",
            "justice_change_rank",
            "justice_remove",

            "health_manage",
            "health_view",
            "health_add",
            "health_edit",
            "health_delete",
            "health_assign_rank",
            "health_change_rank",
            "health_remove",

            "gangs_manage",
            "gangs_view",
            "gangs_add",
            "gangs_edit",
            "gangs_delete",
            "gangs_add_members",
            "gangs_remove_members",
            "gangs_change_leader",

            "users_view",
            "users_edit",
            "users_ban",
            "users_unban",
            "users_disable",
            "users_enable",

            "permissions_view",
            "permissions_give",
            "permissions_remove",
            "permissions_edit",

            "logs_view",
            "logs_search",

            "admins_manage",
            "admins_add",
            "admins_remove",
            "admins_all_permissions",
            "admins_all_sections"
        }
    },

    "founder": {
        "name": "Founder",
        "permissions": {
            "characters_view_all",
            "characters_view_details",
            "characters_edit_all",
            "characters_hide",
            "characters_show",

            "police_manage",
            "police_view",
            "police_add",
            "police_edit",
            "police_assign_rank",
            "police_change_rank",
            "police_remove",

            "justice_manage",
            "justice_view",
            "justice_add",
            "justice_edit",
            "justice_assign_rank",
            "justice_change_rank",
            "justice_remove",

            "health_manage",
            "health_view",
            "health_add",
            "health_edit",
            "health_assign_rank",
            "health_change_rank",
            "health_remove",

            "gangs_manage",
            "gangs_view",
            "gangs_add_members",
            "gangs_remove_members",
            "gangs_change_leader",

            "users_view",
            "users_edit",

            "permissions_view",
            "permissions_give",
            "permissions_edit",

            "logs_view",

            "admins_manage",
            "admins_add"
        }
    },

    "super_admin": {
        "name": "Super Admin",
        "permissions": {
            "characters_view_all",
            "characters_view_details",
            "characters_edit_all",
            "characters_hide",
            "characters_show",

            "police_manage",
            "police_view",
            "police_add",
            "police_edit",
            "police_assign_rank",
            "police_change_rank",
            "police_remove",

            "justice_manage",
            "justice_view",
            "justice_add",
            "justice_edit",
            "justice_assign_rank",
            "justice_change_rank",
            "justice_remove",

            "health_manage",
            "health_view",
            "health_add",
            "health_edit",
            "health_assign_rank",
            "health_change_rank",
            "health_remove",

            "gangs_manage",
            "gangs_view",
            "gangs_add_members",
            "gangs_remove_members",
            "gangs_change_leader",

            "users_view",
            "users_edit",
            "users_ban",
            "users_unban",
            "users_disable",
            "users_enable",

            "permissions_view",
            "permissions_give",
            "permissions_remove",
            "permissions_edit",

            "logs_view",
            "logs_search",

            "admins_manage",
            "admins_add",
            "admins_remove"
        }
    },

    "admin": {
        "name": "Admin",
        "permissions": {
            "characters_view_all",
            "characters_view_details",

            "police_view",
            "police_manage",
            "police_assign_rank",
            "police_change_rank",

            "justice_view",
            "justice_manage",
            "justice_assign_rank",
            "justice_change_rank",

            "health_view",
            "health_manage",
            "health_assign_rank",
            "health_change_rank",

            "gangs_view",
            "gangs_manage",
            "gangs_add_members",
            "gangs_remove_members",
            "gangs_change_leader",

            "users_view",

            "permissions_view",
            "permissions_give",

            "logs_view",

            "admins_manage"
        }
    },

    "moderator": {
        "name": "Moderator",
        "permissions": {
            "characters_view_all",
            "characters_view_details",
            "characters_hide",
            "characters_show",

            "police_view",
            "justice_view",
            "health_view",
            "gangs_view",

            "logs_view"
        }
    },

    "supervisor": {
        "name": "Supervisor",
        "permissions": {
            "characters_view_all",
            "characters_view_details",
            "characters_hide",
            "characters_show",

            "police_view",
            "police_assign_rank",
            "police_change_rank",

            "justice_view",
            "justice_assign_rank",
            "justice_change_rank",

            "health_view",
            "health_assign_rank",
            "health_change_rank",

            "gangs_view",
            "gangs_change_leader"
        }
    },

    "manager": {
        "name": "Manager",
        "permissions": {
            "characters_view_all",
            "characters_view_details",

            "police_view",
            "justice_view",
            "health_view",
            "gangs_view",

            "users_view"
        }
    },

    "department_manager": {
        "name": "Department Manager",
        "permissions": {
            "characters_view_all",
            "characters_view_details",

            "police_manage",
            "police_view",
            "police_add",
            "police_edit",
            "police_assign_rank",
            "police_change_rank",
            "police_remove",

            "justice_manage",
            "justice_view",
            "justice_add",
            "justice_edit",
            "justice_assign_rank",
            "justice_change_rank",
            "justice_remove",

            "health_manage",
            "health_view",
            "health_add",
            "health_edit",
            "health_assign_rank",
            "health_change_rank",
            "health_remove"
        }
    },

    "police_director": {
        "name": "Police Director",
        "permissions": {
            "characters_view_all",
            "characters_view_details",
            "police_manage",
            "police_view",
            "police_add",
            "police_edit",
            "police_assign_rank",
            "police_change_rank",
            "police_remove"
        }
    },

    "justice_director": {
        "name": "Justice Director",
        "permissions": {
            "characters_view_all",
            "characters_view_details",
            "justice_manage",
            "justice_view",
            "justice_add",
            "justice_edit",
            "justice_assign_rank",
            "justice_change_rank",
            "justice_remove"
        }
    },

    "health_director": {
        "name": "Health Director",
        "permissions": {
            "characters_view_all",
            "characters_view_details",
            "health_manage",
            "health_view",
            "health_add",
            "health_edit",
            "health_assign_rank",
            "health_change_rank",
            "health_remove"
        }
    },

    "gang_manager": {
        "name": "Gang Manager",
        "permissions": {
            "characters_view_all",
            "characters_view_details",
            "gangs_manage",
            "gangs_view",
            "gangs_add_members",
            "gangs_remove_members",
            "gangs_change_leader"
        }
    },

    "police_supervisor": {
        "name": "Police Supervisor",
        "permissions": {
            "characters_view_all",
            "characters_view_details",
            "police_view",
            "police_assign_rank",
            "police_change_rank"
        }
    },

    "justice_supervisor": {
        "name": "Justice Supervisor",
        "permissions": {
            "characters_view_all",
            "characters_view_details",
            "justice_view",
            "justice_assign_rank",
            "justice_change_rank"
        }
    },

    "health_supervisor": {
        "name": "Health Supervisor",
        "permissions": {
            "characters_view_all",
            "characters_view_details",
            "health_view",
            "health_assign_rank",
            "health_change_rank"
        }
    },

    "gang_supervisor": {
        "name": "Gang Supervisor",
        "permissions": {
            "characters_view_all",
            "characters_view_details",
            "gangs_view",
            "gangs_change_leader"
        }
    },

    "senior_staff": {
        "name": "Senior Staff",
        "permissions": {
            "characters_view_all",
            "characters_view_details",
            "police_view",
            "justice_view",
            "health_view",
            "gangs_view",
            "users_view",
            "logs_view"
        }
    },

    "staff": {
        "name": "Staff",
        "permissions": {
            "characters_view_all",
            "characters_view_details",
            "police_view",
            "justice_view",
            "health_view",
            "gangs_view"
        }
    },

    "helper": {
        "name": "Helper",
        "permissions": {
            "characters_view_details"
        }
    }
}

# =========================================================
# الأقسام
# =========================================================

DEPARTMENTS = {
    "police": "الشرطة",
    "justice": "وزارة العدل",
    "health": "الصحة",
    "gangs": "العصابات"
}

SECTION_KEYS = {
    "characters": "الشخصيات",
    "police": "الشرطة",
    "justice": "وزارة العدل",
    "health": "الصحة",
    "gangs": "العصابات",
    "users": "المستخدمون",
    "permissions": "الصلاحيات",
    "logs": "السجلات",
    "admin": "الإدارة",
    "settings": "الإعدادات"
}

# =========================================================
# رتب الأقسام
# =========================================================

DEPARTMENT_RANKS = {

    "police": [
        "جندي مستجد",
        "جندي",
        "جندي أول",
        "عريف",
        "وكيل رقيب",
        "رقيب",
        "رقيب أول",
        "رئيس رقباء",
        "ملازم",
        "ملازم أول",
        "نقيب",
        "رائد",
        "مقدم",
        "عقيد",
        "عميد",
        "لواء",
        "فريق",
        "فريق أول",
        "جنرال"
    ],

    "justice": [
        "معالي وزير العدل",
        "نائب وزير العدل",
        "رئيس المحكمة",
        "قاضي أول",
        "قاضي",
        "وكيل نيابة",
        "محامي عام",
        "محامي",
        "مستشار قانوني",
        "باحث قضائي"
    ],

    "health": [
        "متدرب",
        "ممرض",
        "ممرض أول",
        "طبيب عام",
        "طبيب مقيم",
        "طبيب أخصائي",
        "طبيب استشاري",
        "مدير طبي",
        "نائب وزير الصحة",
        "وزير الصحة"
    ],

    "gangs": [
        "Scrap Boss",
        "Scrap Co-Boss",
        "Scrap Member",
        "Death Line Boss",
        "Death Line Co-Boss",
        "Death Line Member",
        "Trickster Boss",
        "Trickster Co-Boss",
        "Trickster Member"
    ]
}

# =========================================================
# العصابات
# =========================================================

GANGS = {

    "scrap": {
        "name": "Scrap",
        "ranks": [
            "Scrap Boss",
            "Scrap Co-Boss",
            "Scrap Member"
        ]
    },

    "death_line": {
        "name": "Death Line",
        "ranks": [
            "Death Line Boss",
            "Death Line Co-Boss",
            "Death Line Member"
        ]
    },

    "trickster": {
        "name": "Trickster",
        "ranks": [
            "Trickster Boss",
            "Trickster Co-Boss",
            "Trickster Member"
        ]
    }
}

# =========================================================
# قاعدة البيانات
# =========================================================

def get_db():

    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    return db


def init_db():

    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_banned INTEGER DEFAULT 0,
            is_disabled INTEGER DEFAULT 0,
            is_owner INTEGER DEFAULT 0,
            role TEXT DEFAULT 'helper',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    user_columns = [
        row["name"]
        for row in db.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    ]

    if "role" not in user_columns:

        db.execute("""
            ALTER TABLE users
            ADD COLUMN role TEXT DEFAULT 'helper'
        """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            first_name TEXT NOT NULL,
            second_name TEXT NOT NULL,
            full_name TEXT NOT NULL,
            full_name_key TEXT UNIQUE NOT NULL,
            country TEXT NOT NULL,
            nationality TEXT NOT NULL,
            birth_date TEXT NOT NULL,
            owner_token TEXT,
            hidden INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE SET NULL
        )
    """)

    character_columns = [
        row["name"]
        for row in db.execute(
            "PRAGMA table_info(characters)"
        ).fetchall()
    ]

    if "owner_token" not in character_columns:

        db.execute("""
            ALTER TABLE characters
            ADD COLUMN owner_token TEXT
        """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS user_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            UNIQUE(user_id, permission),
            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS character_departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            department TEXT NOT NULL,
            UNIQUE(character_id, department),
            FOREIGN KEY(character_id)
                REFERENCES characters(id)
                ON DELETE CASCADE
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS character_ranks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            department TEXT NOT NULL,
            rank_name TEXT NOT NULL,
            UNIQUE(character_id, department),
            FOREIGN KEY(character_id)
                REFERENCES characters(id)
                ON DELETE CASCADE
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE SET NULL
        )
    """)

    log_columns = [
        row["name"]
        for row in db.execute(
            "PRAGMA table_info(activity_logs)"
        ).fetchall()
    ]

    if "details" not in log_columns:

        db.execute("""
            ALTER TABLE activity_logs
            ADD COLUMN details TEXT
        """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS character_admin_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER UNIQUE NOT NULL,
            user_id INTEGER,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(character_id)
                REFERENCES characters(id)
                ON DELETE CASCADE,
            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE SET NULL
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS character_gangs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            gang_key TEXT NOT NULL,
            rank_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(character_id, gang_key),
            FOREIGN KEY(character_id)
                REFERENCES characters(id)
                ON DELETE CASCADE
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS custom_admin_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_key TEXT UNIQUE NOT NULL,
            role_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS custom_role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            UNIQUE(role_id, permission),
            FOREIGN KEY(role_id)
                REFERENCES custom_admin_roles(id)
                ON DELETE CASCADE
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS custom_role_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER NOT NULL,
            section TEXT NOT NULL,
            UNIQUE(role_id, section),
            FOREIGN KEY(role_id)
                REFERENCES custom_admin_roles(id)
                ON DELETE CASCADE
        )
    """)

    db.commit()
    db.close()


# =========================================================
# إنشاء Owner
# =========================================================

def create_owner():

    username = os.environ.get(
        "MT_ADMIN_USERNAME",
        "admin"
    )

    password = os.environ.get(
        "MT_ADMIN_PASSWORD",
        "CHANGE_THIS_PASSWORD"
    )

    db = get_db()

    owner = db.execute("""
        SELECT *
        FROM users
        WHERE is_owner = 1
        LIMIT 1
    """).fetchone()

    if not owner:

        db.execute("""
            INSERT INTO users
            (
                username,
                password_hash,
                is_owner,
                role
            )
            VALUES (?, ?, 1, 'owner')
        """, (
            username,
            generate_password_hash(password)
        ))

    else:

        db.execute("""
            UPDATE users
            SET
                is_owner = 1,
                role = 'owner'
            WHERE id = ?
        """, (
            owner["id"],
        ))

    db.commit()
    db.close()


# =========================================================
# ملكية الشخصيات للزائر
# =========================================================

def get_guest_owner_token():

    token = session.get("guest_owner_token")

    if not token:

        token = secrets.token_urlsafe(32)

        session["guest_owner_token"] = token

    return token


# =========================================================
# المستخدم الحالي
# =========================================================

def current_user():

    user_id = session.get("user_id")

    if not user_id:
        return None

    db = get_db()

    user = db.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (
        user_id,
    )).fetchone()

    db.close()

    return user


# =========================================================
# الرتب المخصصة
# =========================================================

def get_custom_role(role_key):

    if not role_key:
        return None

    db = get_db()

    role = db.execute("""
        SELECT *
        FROM custom_admin_roles
        WHERE role_key = ?
        LIMIT 1
    """, (
        role_key,
    )).fetchone()

    db.close()

    return role


def role_display_name(role_key):

    if role_key == "owner":
        return "Owner"

    if role_key in ROLES:
        return ROLES[role_key]["name"]

    role = get_custom_role(role_key)

    if role:
        return role["role_name"]

    return "بدون رتبة"


# =========================================================
# صلاحيات الرتبة
# =========================================================

def get_role_permissions(user):

    if not user:
        return set()

    if user["is_owner"]:
        return set(PERMISSIONS.keys())

    role_key = user["role"] or "helper"

    if role_key in ROLES:

        return {
            permission
            for permission in ROLES[role_key]["permissions"]
            if permission in PERMISSIONS
        }

    role = get_custom_role(role_key)

    if not role:
        return set()

    db = get_db()

    rows = db.execute("""
        SELECT permission
        FROM custom_role_permissions
        WHERE role_id = ?
    """, (
        role["id"],
    )).fetchall()

    db.close()

    return {
        row["permission"]
        for row in rows
        if row["permission"] in PERMISSIONS
    }


# =========================================================
# أقسام الرتبة
# =========================================================

def get_role_sections(user):

    if not user:
        return set()

    if user["is_owner"]:
        return set(SECTION_KEYS.keys())

    role_key = user["role"] or "helper"

    if role_key in ROLES:

        permissions = get_role_permissions(user)

        sections = set()

        prefix_map = {
            "characters": "characters_",
            "police": "police_",
            "justice": "justice_",
            "health": "health_",
            "gangs": "gangs_",
            "users": "users_",
            "permissions": "permissions_",
            "logs": "logs_",
            "admin": "admins_",
            "settings": "site_"
        }

        for section, prefix in prefix_map.items():

            if any(
                permission.startswith(prefix)
                for permission in permissions
            ):
                sections.add(section)

        if (
            "admins_manage" in permissions
            or "admins_all_sections" in permissions
        ):
            sections.add("admin")

        return {
            section
            for section in sections
            if section in SECTION_KEYS
        }

    role = get_custom_role(role_key)

    if not role:
        return set()

    db = get_db()

    rows = db.execute("""
        SELECT section
        FROM custom_role_sections
        WHERE role_id = ?
    """, (
        role["id"],
    )).fetchall()

    db.close()

    return {
        row["section"]
        for row in rows
        if row["section"] in SECTION_KEYS
    }


# =========================================================
# فحص الصلاحيات
# =========================================================

def has_permission(permission):

    user = current_user()

    if not user:
        return False

    if user["is_owner"]:
        return True

    if permission in get_role_permissions(user):
        return True

    db = get_db()

    row = db.execute("""
        SELECT id
        FROM user_permissions
        WHERE user_id = ?
        AND permission = ?
        LIMIT 1
    """, (
        user["id"],
        permission
    )).fetchone()

    db.close()

    return row is not None


def has_section_access(section):

    user = current_user()

    if not user:
        return False

    if user["is_owner"]:
        return True

    return section in get_role_sections(user)


# =========================================================
# Decorators
# =========================================================

def permission_required(permission):

    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):

            if not current_user():

                return redirect(
                    url_for("login")
                )

            if not has_permission(permission):

                flash(
                    "لا تملك الصلاحية المطلوبة."
                )

                return redirect(
                    url_for("home")
                )

            return function(
                *args,
                **kwargs
            )

        return wrapper

    return decorator


def section_required(section):

    def decorator(function):

        @wraps(function)
        def wrapper(*args, **kwargs):

            if not current_user():

                return redirect(
                    url_for("login")
                )

            if not has_section_access(section):

                flash(
                    "لا تملك صلاحية دخول هذا القسم."
                )

                return redirect(
                    url_for("home")
                )

            return function(
                *args,
                **kwargs
            )

        return wrapper

    return decorator


# =========================================================
# السجلات
# =========================================================

def log_action(action, details=None):

    user = current_user()

    if not user:
        return

    db = get_db()

    db.execute("""
        INSERT INTO activity_logs
        (
            user_id,
            action,
            details
        )
        VALUES (?, ?, ?)
    """, (
        user["id"],
        action,
        details
    ))

    db.commit()
    db.close()


# =========================================================
# تطبيع الأسماء
# =========================================================

def normalize_name(name):

    name = name or ""
    name = name.strip()

    name = name.replace("أ", "ا").replace(
        "إ", "ا"
    ).replace(
        "آ", "ا"
    ).replace(
        "ة", "ه"
    ).replace(
        "ى", "ي"
    )

    name = name.replace("ـ", "")

    name = re.sub(
        r"\s+",
        " ",
        name
    )

    return name.casefold()


# =========================================================
# إنشاء مفتاح رتبة مخصصة
# =========================================================

def make_custom_role_key(role_name):

    slug = re.sub(
        r"[^a-zA-Z0-9]+",
        "_",
        role_name
    ).strip("_").lower()

    if not slug:
        slug = "role"

    token = secrets.token_hex(4)

    return f"custom_{slug}_{token}"


# =========================================================
# الصفحة الرئيسية
# =========================================================

@app.route("/")
def home():

    user = current_user()

    return render_template(
        "index.html",
        current_user=user,
        user=user,
        has_permission=has_permission,
        has_section_access=has_section_access,
        SECTION_KEYS=SECTION_KEYS
    )


# =========================================================
# تسجيل الدخول
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    user = current_user()

    if user:

        return redirect(
            url_for("home")
        )

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        db = get_db()

        user = db.execute("""
            SELECT *
            FROM users
            WHERE username = ?
        """, (
            username,
        )).fetchone()

        db.close()

        if not user:

            flash(
                "اسم المستخدم أو كلمة المرور غير صحيحة."
            )

            return render_template(
                "login.html"
            )

        if user["is_banned"]:

            flash(
                "هذا الحساب محظور."
            )

            return render_template(
                "login.html"
            )

        if user["is_disabled"]:

            flash(
                "هذا الحساب معطل."
            )

            return render_template(
                "login.html"
            )

        if not check_password_hash(
            user["password_hash"],
            password
        ):

            flash(
                "اسم المستخدم أو كلمة المرور غير صحيحة."
            )

            return render_template(
                "login.html"
            )

        guest_token = session.get(
            "guest_owner_token"
        )

        session.clear()

        session.permanent = True

        if guest_token:

            session["guest_owner_token"] = guest_token

        session["user_id"] = user["id"]

        log_action(
            "تسجيل الدخول"
        )

        return redirect(
            url_for("home")
        )

    return render_template(
        "login.html"
    )


# =========================================================
# إنشاء حساب
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if len(username) < 3:

            flash(
                "اسم المستخدم يجب أن يكون 3 أحرف على الأقل."
            )

            return render_template(
                "register.html"
            )

        if len(password) < 6:

            flash(
                "كلمة المرور يجب أن تكون 6 أحرف على الأقل."
            )

            return render_template(
                "register.html"
            )

        if password != confirm_password:

            flash(
                "كلمتا المرور غير متطابقتين."
            )

            return render_template(
                "register.html"
            )

        db = get_db()

        exists = db.execute("""
            SELECT id
            FROM users
            WHERE username = ?
        """, (
            username,
        )).fetchone()

        if exists:

            db.close()

            flash(
                "اسم المستخدم موجود مسبقًا."
            )

            return render_template(
                "register.html"
            )

        cursor = db.execute("""
            INSERT INTO users
            (
                username,
                password_hash,
                role,
                is_owner
            )
            VALUES (?, ?, 'helper', 0)
        """, (
            username,
            generate_password_hash(password)
        ))

        user_id = cursor.lastrowid

        db.commit()
        db.close()

        guest_token = session.get(
            "guest_owner_token"
        )

        session.clear()

        session.permanent = True

        if guest_token:

            session["guest_owner_token"] = guest_token

        session["user_id"] = user_id

        log_action(
            "إنشاء حساب جديد"
        )

        flash(
            "تم إنشاء الحساب بنجاح."
        )

        return redirect(
            url_for("register_character")
        )

    return render_template(
        "register.html"
    )


# =========================================================
# تسجيل الخروج
# =========================================================

@app.route("/logout")
def logout():

    guest_token = session.get(
        "guest_owner_token"
    )

    session.clear()

    if guest_token:

        session["guest_owner_token"] = guest_token

    return redirect(
        url_for("home")
    )


# =========================================================
# تسجيل شخصية
# =========================================================

@app.route(
    "/characters/register",
    methods=["GET", "POST"]
)
def register_character():

    if request.method == "POST":

        first_name = request.form.get(
            "first_name",
            ""
        ).strip()

        second_name = request.form.get(
            "second_name",
            ""
        ).strip()

        country = request.form.get(
            "country",
            ""
        ).strip()

        nationality = request.form.get(
            "nationality",
            ""
        ).strip()

        birth_date = request.form.get(
            "birth_date",
            ""
        ).strip()

        if not all([
            first_name,
            second_name,
            country,
            nationality,
            birth_date
        ]):

            flash(
                "يرجى تعبئة جميع البيانات."
            )

            return render_template(
                "register_character.html"
            )

        full_name = f"{first_name} {second_name}"

        full_name_key = normalize_name(
            full_name
        )

        owner_token = get_guest_owner_token()

        user = current_user()

        db = get_db()

        exists = db.execute("""
            SELECT id
            FROM characters
            WHERE full_name_key = ?
        """, (
            full_name_key,
        )).fetchone()

        if exists:

            db.close()

            flash(
                "هذه الشخصية موجودة مسبقًا."
            )

            return render_template(
                "register_character.html"
            )

        cursor = db.execute("""
            INSERT INTO characters
            (
                user_id,
                first_name,
                second_name,
                full_name,
                full_name_key,
                country,
                nationality,
                birth_date,
                owner_token,
                hidden
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            user["id"] if user else None,
            first_name,
            second_name,
            full_name,
            full_name_key,
            country,
            nationality,
            birth_date,
            owner_token
        ))

        character_id = cursor.lastrowid

        db.execute("""
            INSERT OR IGNORE INTO
            character_ranks
            (
                character_id,
                department,
                rank_name
            )
            VALUES (?, 'general', 'يوجد شخصية')
        """, (
            character_id,
        ))

        db.commit()
        db.close()

        log_action(
            f"إنشاء شخصية: {full_name}"
        )

        flash(
            f"تم تسجيل الشخصية {full_name} بنجاح."
        )

        return redirect(
            url_for(
                "character_details",
                character_id=character_id
            )
        )

    return render_template(
        "register_character.html"
    )


# =========================================================
# الشخصيات
# =========================================================

@app.route("/characters")
def characters():

    user = current_user()

    guest_token = get_guest_owner_token()

    db = get_db()

    admin_view = bool(
        user
        and has_permission(
            "characters_view_all"
        )
    )

    if admin_view:

        rows = db.execute("""
            SELECT *
            FROM characters
            ORDER BY id DESC
        """).fetchall()

    elif user:

        rows = db.execute("""
            SELECT *
            FROM characters
            WHERE
                (
                    user_id = ?
                    OR owner_token = ?
                )
                AND hidden = 0
            ORDER BY id DESC
        """, (
            user["id"],
            guest_token
        )).fetchall()

    else:

        rows = db.execute("""
            SELECT *
            FROM characters
            WHERE owner_token = ?
            AND hidden = 0
            ORDER BY id DESC
        """, (
            guest_token,
        )).fetchall()

    character_data = []

    for character in rows:

        rank_row = db.execute("""
            SELECT rank_name
            FROM character_ranks
            WHERE character_id = ?
            AND department = 'general'
            LIMIT 1
        """, (
            character["id"],
        )).fetchone()

        departments = db.execute("""
            SELECT department
            FROM character_departments
            WHERE character_id = ?
        """, (
            character["id"],
        )).fetchall()

        ranks = db.execute("""
            SELECT department, rank_name
            FROM character_ranks
            WHERE character_id = ?
        """, (
            character["id"],
        )).fetchall()

        gangs = db.execute("""
            SELECT gang_key, rank_name
            FROM character_gangs
            WHERE character_id = ?
        """, (
            character["id"],
        )).fetchall()

        character_data.append({
            "character": character,
            "general_rank": (
                rank_row["rank_name"]
                if rank_row
                else "يوجد شخصية"
            ),
            "departments": departments,
            "ranks": ranks,
            "gangs": gangs
        })

    db.close()

    return render_template(
        "characters.html",
        characters=character_data,
        admin_view=admin_view,
        can_edit_all=has_permission(
            "characters_edit_all"
        ),
        can_delete_all=has_permission(
            "characters_delete_all"
        ),
        can_manage_sections=has_permission(
            "admins_all_sections"
        ),
        user=user,
        DEPARTMENTS=DEPARTMENTS,
        DEPARTMENT_RANKS=DEPARTMENT_RANKS,
        GANGS=GANGS
    )


# =========================================================
# تفاصيل الشخصية
# =========================================================

@app.route(
    "/characters/<int:character_id>"
)
def character_details(character_id):

    user = current_user()

    guest_token = get_guest_owner_token()

    db = get_db()

    character = db.execute("""
        SELECT *
        FROM characters
        WHERE id = ?
    """, (
        character_id,
    )).fetchone()

    if not character:

        db.close()

        flash(
            "الشخصية غير موجودة."
        )

        return redirect(
            url_for("characters")
        )

    is_owner = bool(
        user
        and character["user_id"] == user["id"]
    ) or (
        character["owner_token"]
        and character["owner_token"] == guest_token
    )

    can_view_all = bool(
        user
        and has_permission(
            "characters_view_all"
        )
    )

    if not is_owner and not can_view_all:

        db.close()

        flash(
            "لا تملك صلاحية مشاهدة هذه الشخصية."
        )

        return redirect(
            url_for("characters")
        )

    if character["hidden"] and not can_view_all:

        db.close()

        flash(
            "هذه الشخصية مخفية."
        )

        return redirect(
            url_for("characters")
        )

    departments = db.execute("""
        SELECT
            character_departments.department,
            character_ranks.rank_name

        FROM character_departments

        LEFT JOIN character_ranks
        ON character_ranks.character_id =
           character_departments.character_id

        AND character_ranks.department =
            character_departments.department

        WHERE character_departments.character_id = ?
    """, (
        character_id,
    )).fetchall()

    gangs = db.execute("""
        SELECT
            gang_key,
            rank_name
        FROM character_gangs
        WHERE character_id = ?
    """, (
        character_id,
    )).fetchall()

    general_rank = db.execute("""
        SELECT rank_name
        FROM character_ranks
        WHERE character_id = ?
        AND department = 'general'
        LIMIT 1
    """, (
        character_id,
    )).fetchone()

    db.close()

    return render_template(
        "character_details.html",
        character=character,
        departments=departments,
        gangs=gangs,
        general_rank=(
            general_rank["rank_name"]
            if general_rank
            else "يوجد شخصية"
        ),
        user=user,
        GANGS=GANGS
    )


# =========================================================
# حذف شخصية
# =========================================================

@app.route(
    "/characters/<int:character_id>/delete",
    methods=["POST"]
)
@permission_required(
    "characters_delete_all"
)
def delete_character(character_id):

    db = get_db()

    character = db.execute("""
        SELECT *
        FROM characters
        WHERE id = ?
    """, (
        character_id,
    )).fetchone()

    if not character:

        db.close()

        flash(
            "الشخصية غير موجودة."
        )

        return redirect(
            url_for("characters")
        )

    db.execute("""
        DELETE FROM characters
        WHERE id = ?
    """, (
        character_id,
    ))

    db.commit()
    db.close()

    log_action(
        f"حذف الشخصية {character['full_name']}"
    )

    flash(
        "تم حذف الشخصية."
    )

    return redirect(
        url_for("characters")
    )


# =========================================================
# تعديل شخصية
# =========================================================

@app.route(
    "/admin/characters/<int:character_id>/edit",
    methods=["POST"]
)
@permission_required(
    "characters_edit_all"
)
def edit_character(character_id):

    first_name = request.form.get(
        "first_name",
        ""
    ).strip()

    second_name = request.form.get(
        "second_name",
        ""
    ).strip()

    country = request.form.get(
        "country",
        ""
    ).strip()

    nationality = request.form.get(
        "nationality",
        ""
    ).strip()

    birth_date = request.form.get(
        "birth_date",
        ""
    ).strip()

    if not all([
        first_name,
        second_name,
        country,
        nationality,
        birth_date
    ]):

        flash(
            "جميع بيانات الشخصية مطلوبة."
        )

        return redirect(
            url_for("characters")
        )

    full_name = f"{first_name} {second_name}"

    full_name_key = normalize_name(
        full_name
    )

    db = get_db()

    exists = db.execute("""
        SELECT id
        FROM characters
        WHERE full_name_key = ?
        AND id != ?
    """, (
        full_name_key,
        character_id
    )).fetchone()

    if exists:

        db.close()

        flash(
            "اسم الشخصية مستخدم مسبقًا."
        )

        return redirect(
            url_for("characters")
        )

    db.execute("""
        UPDATE characters
        SET
            first_name = ?,
            second_name = ?,
            full_name = ?,
            full_name_key = ?,
            country = ?,
            nationality = ?,
            birth_date = ?
        WHERE id = ?
    """, (
        first_name,
        second_name,
        full_name,
        full_name_key,
        country,
        nationality,
        birth_date,
        character_id
    ))

    db.commit()
    db.close()

    log_action(
        f"تعديل الشخصية: {full_name}"
    )

    flash(
        "تم تعديل الشخصية."
    )

    return redirect(
        url_for("characters")
    )


# =========================================================
# إخفاء شخصية
# =========================================================

@app.route(
    "/admin/characters/<int:character_id>/hide",
    methods=["POST"]
)
@permission_required(
    "characters_hide"
)
def hide_character(character_id):

    db = get_db()

    db.execute("""
        UPDATE characters
        SET hidden = 1
        WHERE id = ?
    """, (
        character_id,
    ))

    db.commit()
    db.close()

    log_action(
        f"إخفاء الشخصية رقم {character_id}"
    )

    flash(
        "تم إخفاء الشخصية."
    )

    return redirect(
        url_for("characters")
    )


# =========================================================
# إظهار شخصية
# =========================================================

@app.route(
    "/admin/characters/<int:character_id>/show",
    methods=["POST"]
)
@permission_required(
    "characters_show"
)
def show_character(character_id):

    db = get_db()

    db.execute("""
        UPDATE characters
        SET hidden = 0
        WHERE id = ?
    """, (
        character_id,
    ))

    db.commit()
    db.close()

    log_action(
        f"إظهار الشخصية رقم {character_id}"
    )

    flash(
        "تم إظهار الشخصية."
    )

    return redirect(
        url_for("characters")
    )


# =========================================================
# تعيين شخصية إلى قسم
# =========================================================

@app.route(
    "/admin/characters/<int:character_id>/department",
    methods=["POST"]
)
def assign_department(character_id):

    department = request.form.get(
        "department",
        ""
    ).strip()

    if department not in DEPARTMENTS:

        flash(
            "القسم غير صحيح."
        )

        return redirect(
            url_for("characters")
        )

    if not (
        has_permission(
            f"{department}_manage"
        )
        or has_permission(
            f"{department}_add"
        )
        or has_permission(
            "admins_all_sections"
        )
    ):

        flash(
            "لا تملك صلاحية إدارة هذا القسم."
        )

        return redirect(
            url_for("characters")
        )

    db = get_db()

    character = db.execute("""
        SELECT *
        FROM characters
        WHERE id = ?
    """, (
        character_id,
    )).fetchone()

    if not character:

        db.close()

        flash(
            "الشخصية غير موجودة."
        )

        return redirect(
            url_for("characters")
        )

    db.execute("""
        INSERT OR IGNORE INTO
        character_departments
        (
            character_id,
            department
        )
        VALUES (?, ?)
    """, (
        character_id,
        department
    ))

    default_rank = DEPARTMENT_RANKS[department][0]

    db.execute("""
        INSERT OR IGNORE INTO
        character_ranks
        (
            character_id,
            department,
            rank_name
        )
        VALUES (?, ?, ?)
    """, (
        character_id,
        department,
        default_rank
    ))

    db.commit()
    db.close()

    log_action(
        f"تعيين {character['full_name']} إلى "
        f"{DEPARTMENTS[department]} "
        f"برتبته الابتدائية: {default_rank}"
    )

    flash(
        f"تم تعيين الشخصية إلى "
        f"{DEPARTMENTS[department]} "
        f"برتبته {default_rank}."
    )

    return redirect(
        url_for("characters")
    )


# =========================================================
# إزالة الشخصية من القسم
# =========================================================

@app.route(
    "/admin/characters/<int:character_id>/department/remove",
    methods=["POST"]
)
def remove_department(character_id):

    department = request.form.get(
        "department",
        ""
    ).strip()

    if department not in DEPARTMENTS:

        flash(
            "القسم غير صحيح."
        )

        return redirect(
            url_for("characters")
        )

    if not (
        has_permission(
            f"{department}_remove"
        )
        or has_permission(
            f"{department}_manage"
        )
        or has_permission(
            "admins_all_sections"
        )
    ):

        flash(
            "لا تملك صلاحية إزالة الشخصية من القسم."
        )

        return redirect(
            url_for("characters")
        )

    db = get_db()

    db.execute("""
        DELETE FROM character_departments
        WHERE character_id = ?
        AND department = ?
    """, (
        character_id,
        department
    ))

    db.execute("""
        DELETE FROM character_ranks
        WHERE character_id = ?
        AND department = ?
    """, (
        character_id,
        department
    ))

    remaining = db.execute("""
        SELECT COUNT(*)
        FROM character_departments
        WHERE character_id = ?
    """, (
        character_id,
    )).fetchone()[0]

    if remaining == 0:

        db.execute("""
            INSERT OR REPLACE INTO
            character_ranks
            (
                character_id,
                department,
                rank_name
            )
            VALUES (?, ?, ?)
        """, (
            character_id,
            "general",
            "يوجد شخصية"
        ))

    db.commit()
    db.close()

    flash(
        "تمت إزالة الشخصية من القسم."
    )

    return redirect(
        url_for("characters")
    )


# =========================================================
# تغيير رتبة شخصية
# =========================================================

@app.route(
    "/admin/characters/<int:character_id>/rank",
    methods=["POST"]
)
def assign_rank(character_id):

    department = request.form.get(
        "department",
        ""
    ).strip()

    rank = request.form.get(
        "rank",
        ""
    ).strip()

    if not department or not rank:

        flash(
            "بيانات الرتبة ناقصة."
        )

        return redirect(
            url_for("characters")
        )

    if department not in DEPARTMENTS:

        flash(
            "القسم غير صحيح."
        )

        return redirect(
            url_for("characters")
        )

    if rank not in DEPARTMENT_RANKS[department]:

        flash(
            "الرتبة غير صحيحة."
        )

        return redirect(
            url_for("characters")
        )

    if not (
        has_permission(
            f"{department}_change_rank"
        )
        or has_permission(
            f"{department}_assign_rank"
        )
        or has_permission(
            f"{department}_manage"
        )
        or has_permission(
            "admins_all_sections"
        )
    ):

        flash(
            "لا تملك صلاحية تغيير الرتبة."
        )

        return redirect(
            url_for("characters")
        )

    db = get_db()

    character = db.execute("""
        SELECT *
        FROM characters
        WHERE id = ?
    """, (
        character_id,
    )).fetchone()

    if not character:

        db.close()

        flash(
            "الشخصية غير موجودة."
        )

        return redirect(
            url_for("characters")
        )

    exists = db.execute("""
        SELECT id
        FROM character_departments
        WHERE character_id = ?
        AND department = ?
    """, (
        character_id,
        department
    )).fetchone()

    if not exists:

        db.close()

        flash(
            "الشخصية ليست في هذا القسم."
        )

        return redirect(
            url_for("characters")
        )

    db.execute("""
        INSERT OR REPLACE INTO
        character_ranks
        (
            character_id,
            department,
            rank_name
        )
        VALUES (?, ?, ?)
    """, (
        character_id,
        department,
        rank
    ))

    db.commit()
    db.close()

    log_action(
        f"تغيير رتبة الشخصية "
        f"{character['full_name']} "
        f"في {DEPARTMENTS[department]} "
        f"إلى {rank}"
    )

    flash(
        f"تم تغيير الرتبة إلى {rank}."
    )

    return redirect(
        url_for("characters")
    )


# =========================================================
# شخصيات قسم
# =========================================================

def get_department_characters(department):

    db = get_db()

    characters = db.execute("""
        SELECT
            characters.*,
            character_ranks.rank_name

        FROM characters

        JOIN character_departments

        ON character_departments.character_id =
           characters.id

        LEFT JOIN character_ranks

        ON character_ranks.character_id =
           characters.id

        AND character_ranks.department = ?

        WHERE character_departments.department = ?

        AND characters.hidden = 0

        ORDER BY characters.id DESC
    """, (
        department,
        department
    )).fetchall()

    db.close()

    return characters


# =========================================================
# الشرطة
# =========================================================

@app.route("/police")
def police():

    user = current_user()

    characters = []

    if user and (
        has_permission("police_view")
        or has_permission("police_manage")
        or has_section_access("police")
    ):

        characters = get_department_characters(
            "police"
        )

    return render_template(
        "police.html",
        characters=characters,
        user=user,
        ranks=DEPARTMENT_RANKS["police"],
        DEPARTMENT_RANKS=DEPARTMENT_RANKS
    )


# =========================================================
# العدل
# =========================================================

@app.route("/justice")
def justice():

    user = current_user()

    characters = []

    if user and (
        has_permission("justice_view")
        or has_permission("justice_manage")
        or has_section_access("justice")
    ):

        characters = get_department_characters(
            "justice"
        )

    return render_template(
        "justice.html",
        characters=characters,
        user=user,
        ranks=DEPARTMENT_RANKS["justice"],
        DEPARTMENT_RANKS=DEPARTMENT_RANKS
    )


# =========================================================
# الصحة
# =========================================================

@app.route("/health")
def health():

    user = current_user()

    characters = []

    if user and (
        has_permission("health_view")
        or has_permission("health_manage")
        or has_section_access("health")
    ):

        characters = get_department_characters(
            "health"
        )

    return render_template(
        "health.html",
        characters=characters,
        user=user,
        ranks=DEPARTMENT_RANKS["health"],
        DEPARTMENT_RANKS=DEPARTMENT_RANKS
    )


# =========================================================
# العصابات
# =========================================================

@app.route("/gangs")
def gangs():

    user = current_user()

    gang_data = {}

    for gang_key, gang_info in GANGS.items():

        gang_data[gang_key] = {
            "name": gang_info["name"],
            "ranks": gang_info["ranks"],
            "members": []
        }

    if user and (
        has_permission("gangs_view")
        or has_permission("gangs_manage")
        or has_section_access("gangs")
    ):

        db = get_db()

        rows = db.execute("""
            SELECT
                character_gangs.id,
                character_gangs.character_id,
                character_gangs.gang_key,
                character_gangs.rank_name,
                characters.full_name,
                characters.user_id

            FROM character_gangs

            JOIN characters
            ON characters.id =
               character_gangs.character_id

            WHERE characters.hidden = 0

            ORDER BY
                character_gangs.gang_key,
                character_gangs.id DESC
        """).fetchall()

        db.close()

        for row in rows:

            if row["gang_key"] not in gang_data:
                continue

            gang_data[
                row["gang_key"]
            ]["members"].append(row)

    return render_template(
        "gangs.html",
        characters=gang_data,
        gangs=gang_data,
        GANGS=GANGS,
        DEPARTMENT_RANKS=DEPARTMENT_RANKS,
        user=user
    )


# =========================================================
# إعطاء شخصية لعصابة
# =========================================================

@app.route(
    "/admin/characters/<int:character_id>/gang",
    methods=["POST"]
)
def assign_gang(character_id):

    gang_key = request.form.get(
        "gang",
        ""
    ).strip()

    rank = request.form.get(
        "rank",
        ""
    ).strip()

    if gang_key not in GANGS:

        flash(
            "العصابة غير صحيحة."
        )

        return redirect(
            url_for("characters")
        )

    allowed_ranks = GANGS[gang_key]["ranks"]

    if not rank:
        rank = allowed_ranks[-1]

    if rank not in allowed_ranks:

        flash(
            "رتبة العصابة غير صحيحة."
        )

        return redirect(
            url_for("characters")
        )

    if not (
        has_permission("gangs_add_members")
        or has_permission("gangs_add")
        or has_permission("gangs_manage")
        or has_permission("admins_all_sections")
    ):

        flash(
            "لا تملك صلاحية إضافة أعضاء للعصابات."
        )

        return redirect(
            url_for("characters")
        )

    db = get_db()

    character = db.execute("""
        SELECT *
        FROM characters
        WHERE id = ?
    """, (
        character_id,
    )).fetchone()

    if not character:

        db.close()

        flash(
            "الشخصية غير موجودة."
        )

        return redirect(
            url_for("characters")
        )

    db.execute("""
        INSERT INTO character_gangs
        (
            character_id,
            gang_key,
            rank_name
        )
        VALUES (?, ?, ?)

        ON CONFLICT(character_id, gang_key)
        DO UPDATE SET
            rank_name = excluded.rank_name
    """, (
        character_id,
        gang_key,
        rank
    ))

    db.execute("""
        INSERT OR IGNORE INTO
        character_departments
        (
            character_id,
            department
        )
        VALUES (?, 'gangs')
    """, (
        character_id,
    ))

    db.execute("""
        INSERT OR IGNORE INTO
        character_ranks
        (
            character_id,
            department,
            rank_name
        )
        VALUES (?, 'gangs', ?)
    """, (
        character_id,
        rank
    ))

    db.commit()
    db.close()

    log_action(
        f"إضافة {character['full_name']} "
        f"إلى عصابة {GANGS[gang_key]['name']} "
        f"برتبة {rank}"
    )

    flash(
        f"تمت إضافة {character['full_name']} "
        f"إلى {GANGS[gang_key]['name']} "
        f"برتبة {rank}."
    )

    return redirect(
        url_for("characters")
    )


# =========================================================
# تغيير رتبة العصابة
# =========================================================

@app.route(
    "/admin/characters/<int:character_id>/gang/rank",
    methods=["POST"]
)
def change_gang_rank(character_id):

    gang_key = request.form.get(
        "gang",
        ""
    ).strip()

    rank = request.form.get(
        "rank",
        ""
    ).strip()

    if gang_key not in GANGS:

        flash(
            "العصابة غير صحيحة."
        )

        return redirect(
            url_for("characters")
        )

    if rank not in GANGS[gang_key]["ranks"]:

        flash(
            "رتبة العصابة غير صحيحة."
        )

        return redirect(
            url_for("characters")
        )

    if not (
        has_permission("gangs_change_leader")
        or has_permission("gangs_edit")
        or has_permission("gangs_manage")
        or has_permission("admins_all_sections")
    ):

        flash(
            "لا تملك صلاحية تغيير رتبة العصابة."
        )

        return redirect(
            url_for("characters")
        )

    db = get_db()

    character = db.execute("""
        SELECT *
        FROM characters
        WHERE id = ?
    """, (
        character_id,
    )).fetchone()

    if not character:

        db.close()

        flash(
            "الشخصية غير موجودة."
        )

        return redirect(
            url_for("characters")
        )

    membership = db.execute("""
        SELECT id
        FROM character_gangs
        WHERE character_id = ?
        AND gang_key = ?
        LIMIT 1
    """, (
        character_id,
        gang_key
    )).fetchone()

    if not membership:

        db.close()

        flash(
            "الشخصية ليست في هذه العصابة."
        )

        return redirect(
            url_for("characters")
        )

    db.execute("""
        UPDATE character_gangs
        SET rank_name = ?
        WHERE character_id = ?
        AND gang_key = ?
    """, (
        rank,
        character_id,
        gang_key
    ))

    db.execute("""
        UPDATE character_ranks
        SET rank_name = ?
        WHERE character_id = ?
        AND department = 'gangs'
    """, (
        rank,
        character_id
    ))

    db.commit()
    db.close()

    log_action(
        f"تغيير رتبة {character['full_name']} "
        f"في عصابة {GANGS[gang_key]['name']} "
        f"إلى {rank}"
    )

    flash(
        f"تم تغيير رتبة العصابة إلى {rank}."
    )

    return redirect(
        url_for("characters")
    )


# =========================================================
# إزالة شخصية من عصابة
# =========================================================

@app.route(
    "/admin/characters/<int:character_id>/gang/remove",
    methods=["POST"]
)
def remove_gang(character_id):

    gang_key = request.form.get(
        "gang",
        ""
    ).strip()

    if gang_key not in GANGS:

        flash(
            "العصابة غير صحيحة."
        )

        return redirect(
            url_for("characters")
        )

    if not (
        has_permission("gangs_remove_members")
        or has_permission("gangs_manage")
        or has_permission("admins_all_sections")
    ):

        flash(
            "لا تملك صلاحية إزالة العضو."
        )

        return redirect(
            url_for("characters")
        )

    db = get_db()

    character = db.execute("""
        SELECT *
        FROM characters
        WHERE id = ?
    """, (
        character_id,
    )).fetchone()

    if not character:

        db.close()

        flash(
            "الشخصية غير موجودة."
        )

        return redirect(
            url_for("characters")
        )

    db.execute("""
        DELETE FROM character_gangs
        WHERE character_id = ?
        AND gang_key = ?
    """, (
        character_id,
        gang_key
    ))

    remaining_gangs = db.execute("""
        SELECT COUNT(*)
        FROM character_gangs
        WHERE character_id = ?
    """, (
        character_id,
    )).fetchone()[0]

    if remaining_gangs == 0:

        db.execute("""
            DELETE FROM character_departments
            WHERE character_id = ?
            AND department = 'gangs'
        """, (
            character_id,
        ))

        db.execute("""
            DELETE FROM character_ranks
            WHERE character_id = ?
            AND department = 'gangs'
        """, (
            character_id,
        ))

    db.commit()
    db.close()

    log_action(
        f"إزالة {character['full_name']} "
        f"من عصابة {GANGS[gang_key]['name']}"
    )

    flash(
        f"تمت إزالة الشخصية من "
        f"{GANGS[gang_key]['name']}."
    )

    return redirect(
        url_for("characters")
    )


# =========================================================
# الإدارة
# =========================================================

@app.route("/admin")
def admin_panel():

    user = current_user()

    if not user:

        return redirect(
            url_for("login")
        )

    role_permissions = get_role_permissions(
        user
    )

    role_sections = get_role_sections(
        user
    )

    is_admin = bool(
        user["is_owner"]
        or "admin" in role_sections
        or "admins_manage" in role_permissions
        or "admins_add" in role_permissions
        or "permissions_view" in role_permissions
    )

    if not is_admin:

        flash(
            "لا تملك صلاحية دخول الإدارة."
        )

        return redirect(
            url_for("home")
        )

    db = get_db()

    characters = db.execute("""
        SELECT
            characters.id,
            characters.full_name,
            characters.user_id,
            users.username,
            users.role,
            users.is_owner

        FROM characters

        LEFT JOIN users
        ON users.id = characters.user_id

        ORDER BY characters.full_name
    """).fetchall()

    users_list = db.execute("""
        SELECT
            id,
            username,
            role,
            is_owner,
            is_banned,
            is_disabled
        FROM users
        ORDER BY username
    """).fetchall()

    custom_roles = db.execute("""
        SELECT *
        FROM custom_admin_roles
        ORDER BY id DESC
    """).fetchall()

    db.close()

    return render_template(
        "permissions.html",
        characters=characters,
        users=users_list,
        ROLES=ROLES,
        PERMISSIONS=PERMISSIONS,
        custom_roles=custom_roles,
        SECTION_KEYS=SECTION_KEYS,
        current_user=user,
        admin_permissions_page=True,
        role_display_name=role_display_name
    )


# =========================================================
# إعطاء رتبة إدارية لشخصية
# =========================================================

@app.route(
    "/admin/character-role",
    methods=["POST"]
)
def assign_character_admin_role():

    if not (
        has_permission("admins_add")
        or has_permission("permissions_give")
        or has_permission("admins_manage")
    ):

        flash(
            "لا تملك صلاحية إعطاء الرتبة."
        )

        return redirect(
            url_for("admin_panel")
        )

    character_id = request.form.get(
        "character_id",
        ""
    ).strip()

    role_key = request.form.get(
        "role",
        ""
    ).strip()

    if not character_id:

        flash(
            "يجب اختيار الشخصية."
        )

        return redirect(
            url_for("admin_panel")
        )

    role_name = role_display_name(
        role_key
    )

    if role_name == "بدون رتبة":

        flash(
            "الرتبة الإدارية غير صحيحة."
        )

        return redirect(
            url_for("admin_panel")
        )

    db = get_db()

    character = db.execute("""
        SELECT
            characters.*,
            users.username,
            users.is_owner

        FROM characters

        LEFT JOIN users
        ON users.id = characters.user_id

        WHERE characters.id = ?
    """, (
        character_id,
    )).fetchone()

    if not character:

        db.close()

        flash(
            "الشخصية غير موجودة."
        )

        return redirect(
            url_for("admin_panel")
        )

    if not character["user_id"]:

        db.close()

        flash(
            "لا يمكن إعطاء رتبة حسابية لشخصية غير مرتبطة بحساب."
        )

        return redirect(
            url_for("admin_panel")
        )

    current = current_user()

    if (
        character["is_owner"]
        and not current["is_owner"]
    ):

        db.close()

        flash(
            "لا يمكنك تعديل رتبة Owner."
        )

        return redirect(
            url_for("admin_panel")
        )

    if (
        role_key == "owner"
        and not current["is_owner"]
    ):

        db.close()

        flash(
            "فقط Owner يستطيع تعيين Owner."
        )

        return redirect(
            url_for("admin_panel")
        )

    is_owner = (
        1
        if role_key == "owner"
        else 0
    )

    db.execute("""
        UPDATE users
        SET
            role = ?,
            is_owner = ?
        WHERE id = ?
    """, (
        role_key,
        is_owner,
        character["user_id"]
    ))

    db.execute("""
        INSERT INTO character_admin_roles
        (
            character_id,
            user_id,
            role
        )
        VALUES (?, ?, ?)

        ON CONFLICT(character_id)
        DO UPDATE SET
            user_id = excluded.user_id,
            role = excluded.role
    """, (
        character_id,
        character["user_id"],
        role_key
    ))

    db.commit()
    db.close()

    log_action(
        f"تعيين الرتبة "
        f"{role_name} "
        f"للشخصية {character['full_name']}"
    )

    flash(
        f"تم إعطاء الشخصية "
        f"{character['full_name']} "
        f"رتبة {role_name}."
    )

    return redirect(
        url_for("admin_panel")
    )


# =========================================================
# إزالة الرتبة الإدارية
# =========================================================

@app.route(
    "/admin/character-role/remove",
    methods=["POST"]
)
def remove_character_admin_role():

    if not (
        has_permission("admins_remove")
        or has_permission("permissions_remove")
        or has_permission("admins_manage")
    ):

        flash(
            "لا تملك صلاحية إزالة الرتبة."
        )

        return redirect(
            url_for("admin_panel")
        )

    character_id = request.form.get(
        "character_id",
        ""
    ).strip()

    if not character_id:

        flash(
            "الشخصية غير محددة."
        )

        return redirect(
            url_for("admin_panel")
        )

    db = get_db()

    character = db.execute("""
        SELECT
            characters.*,
            users.is_owner

        FROM characters

        LEFT JOIN users
        ON users.id = characters.user_id

        WHERE characters.id = ?
    """, (
        character_id,
    )).fetchone()

    if not character:

        db.close()

        flash(
            "الشخصية غير موجودة."
        )

        return redirect(
            url_for("admin_panel")
        )

    if character["is_owner"]:

        db.close()

        flash(
            "لا يمكن إزالة رتبة Owner."
        )

        return redirect(
            url_for("admin_panel")
        )

    if not character["user_id"]:

        db.close()

        flash(
            "الشخصية غير مرتبطة بحساب."
        )

        return redirect(
            url_for("admin_panel")
        )

    db.execute("""
        UPDATE users
        SET
            role = 'helper',
            is_owner = 0
        WHERE id = ?
    """, (
        character["user_id"],
    ))

    db.execute("""
        DELETE FROM character_admin_roles
        WHERE character_id = ?
    """, (
        character_id,
    ))

    db.execute("""
        DELETE FROM user_permissions
        WHERE user_id = ?
    """, (
        character["user_id"],
    ))

    db.commit()
    db.close()

    log_action(
        f"إزالة الرتبة الإدارية من "
        f"{character['full_name']}"
    )

    flash(
        "تمت إزالة الرتبة الإدارية."
    )

    return redirect(
        url_for("admin_panel")
    )


# =========================================================
# صفحة الصلاحيات
# =========================================================

@app.route("/admin/permissions")
def permissions():

    user = current_user()

    if not user:

        return redirect(
            url_for("login")
        )

    if not (
        has_section_access("permissions")
        or has_permission("permissions_view")
        or has_permission("admins_manage")
    ):

        flash(
            "لا تملك صلاحية فتح الصلاحيات."
        )

        return redirect(
            url_for("home")
        )

    db = get_db()

    users = db.execute("""
        SELECT
            id,
            username,
            is_owner,
            role
        FROM users
        ORDER BY username
    """).fetchall()

    characters = db.execute("""
        SELECT
            characters.id,
            characters.full_name,
            characters.user_id,
            users.username,
            users.role,
            users.is_owner

        FROM characters

        LEFT JOIN users
        ON users.id = characters.user_id

        ORDER BY characters.full_name
    """).fetchall()

    custom_roles = db.execute("""
        SELECT *
        FROM custom_admin_roles
        ORDER BY id DESC
    """).fetchall()

    user_permissions = {}
    user_roles = {}

    for account in users:

        user_roles[
            account["id"]
        ] = (
            "owner"
            if account["is_owner"]
            else (
                account["role"]
                or "helper"
            )
        )

        rows = db.execute("""
            SELECT permission
            FROM user_permissions
            WHERE user_id = ?
        """, (
            account["id"],
        )).fetchall()

        user_permissions[
            account["id"]
        ] = {
            row["permission"]
            for row in rows
        }

    db.close()

    return render_template(
        "permissions.html",
        users=users,
        permissions=PERMISSIONS,
        user_permissions=user_permissions,
        user_roles=user_roles,
        ROLES=ROLES,
        custom_roles=custom_roles,
        SECTION_KEYS=SECTION_KEYS,
        current_user=user,
        selected_user=None,
        selected_permissions=set(),
        characters=characters,
        admin_permissions_page=True,
        role_display_name=role_display_name
    )


# =========================================================
# تحديث صلاحيات مستخدم
# =========================================================

@app.route(
    "/admin/permissions/<int:user_id>",
    methods=["POST"]
)
def update_permissions(user_id):

    if not (
        has_permission("permissions_give")
        or has_permission("permissions_edit")
        or has_permission("admins_all_permissions")
    ):

        flash(
            "لا تملك صلاحية تعديل الصلاحيات."
        )

        return redirect(
            url_for("permissions")
        )

    db = get_db()

    current = db.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (
        session.get("user_id"),
    )).fetchone()

    target = db.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (
        user_id,
    )).fetchone()

    if not current:

        db.close()

        return redirect(
            url_for("login")
        )

    if not target:

        db.close()

        flash(
            "المستخدم غير موجود."
        )

        return redirect(
            url_for("permissions")
        )

    if (
        target["is_owner"]
        and not current["is_owner"]
    ):

        db.close()

        flash(
            "لا يمكنك تعديل مالك الموقع."
        )

        return redirect(
            url_for("permissions")
        )

    role_key = request.form.get(
        "role",
        "helper"
    ).strip()

    valid_builtin = (
        role_key in ROLES
    )

    custom_role = db.execute("""
        SELECT id
        FROM custom_admin_roles
        WHERE role_key = ?
        LIMIT 1
    """, (
        role_key,
    )).fetchone()

    valid_custom = (
        custom_role is not None
    )

    if not valid_builtin and not valid_custom:

        role_key = "helper"

    selected = request.form.getlist(
        "permissions"
    )

    if role_key == "owner":

        if not current["is_owner"]:

            db.close()

            flash(
                "فقط Owner يستطيع تعيين Owner."
            )

            return redirect(
                url_for("permissions")
            )

        db.execute("""
            UPDATE users
            SET
                role = 'owner',
                is_owner = 1
            WHERE id = ?
        """, (
            user_id,
        ))

        db.execute("""
            DELETE FROM user_permissions
            WHERE user_id = ?
        """, (
            user_id,
        ))

        db.commit()
        db.close()

        log_action(
            f"تعيين Owner للمستخدم "
            f"{target['username']}"
        )

        flash(
            f"تم تعيين {target['username']} كـ Owner."
        )

        return redirect(
            url_for("permissions")
        )

    if target["is_owner"]:

        if not current["is_owner"]:

            db.close()

            flash(
                "لا يمكنك تغيير رتبة Owner."
            )

            return redirect(
                url_for("permissions")
            )

        db.execute("""
            UPDATE users
            SET
                is_owner = 0,
                role = ?
            WHERE id = ?
        """, (
            role_key,
            user_id
        ))

    else:

        db.execute("""
            UPDATE users
            SET
                role = ?,
                is_owner = 0
            WHERE id = ?
        """, (
            role_key,
            user_id
        ))

    db.execute("""
        DELETE FROM user_permissions
        WHERE user_id = ?
    """, (
        user_id,
    ))

    for permission in selected:

        if permission not in PERMISSIONS:
            continue

        db.execute("""
            INSERT OR IGNORE INTO
            user_permissions
            (
                user_id,
                permission
            )
            VALUES (?, ?)
        """, (
            user_id,
            permission
        ))

    db.commit()
    db.close()

    log_action(
        f"تحديث رتبة وصلاحيات المستخدم "
        f"{target['username']}"
    )

    flash(
        "تم تحديث الرتبة والصلاحيات."
    )

    return redirect(
        url_for("permissions")
    )


# =========================================================
# إنشاء رتبة مخصصة
# =========================================================

@app.route(
    "/admin/roles/create",
    methods=["POST"]
)
def create_custom_role():

    if not (
        has_permission("admins_add")
        or has_permission("permissions_give")
        or has_permission("admins_manage")
    ):

        flash(
            "لا تملك صلاحية إنشاء رتبة."
        )

        return redirect(
            url_for("admin_panel")
        )

    role_name = request.form.get(
        "role_name",
        ""
    ).strip()

    if not role_name:

        flash(
            "اسم الرتبة مطلوب."
        )

        return redirect(
            url_for("admin_panel")
        )

    permissions = request.form.getlist(
        "permissions"
    )

    sections = request.form.getlist(
        "sections"
    )

    permissions = [
        p for p in permissions
        if p in PERMISSIONS
    ]

    sections = [
        s for s in sections
        if s in SECTION_KEYS
    ]

    db = get_db()

    role_key = make_custom_role_key(
        role_name
    )

    cursor = db.execute("""
        INSERT INTO custom_admin_roles
        (
            role_key,
            role_name
        )
        VALUES (?, ?)
    """, (
        role_key,
        role_name
    ))

    role_id = cursor.lastrowid

    for permission in set(permissions):

        db.execute("""
            INSERT OR IGNORE INTO
            custom_role_permissions
            (
                role_id,
                permission
            )
            VALUES (?, ?)
        """, (
            role_id,
            permission
        ))

    for section in set(sections):

        db.execute("""
            INSERT OR IGNORE INTO
            custom_role_sections
            (
                role_id,
                section
            )
            VALUES (?, ?,)
        """.replace("VALUES (?, ?,)", "VALUES (?, ?)"), (
            role_id,
            section
        ))

    db.commit()
    db.close()

    log_action(
        f"إنشاء رتبة مخصصة: {role_name}"
    )

    flash(
        f"تم إنشاء الرتبة المخصصة {role_name}."
    )

    return redirect(
        url_for("admin_panel")
    )


# =========================================================
# تعديل رتبة مخصصة
# =========================================================

@app.route(
    "/admin/roles/<int:role_id>/update",
    methods=["POST"]
)
def update_custom_role(role_id):

    if not (
        has_permission("permissions_edit")
        or has_permission("admins_manage")
    ):

        flash(
            "لا تملك صلاحية تعديل الرتبة."
        )

        return redirect(
            url_for("admin_panel")
        )

    role_name = request.form.get(
        "role_name",
        ""
    ).strip()

    if not role_name:

        flash(
            "اسم الرتبة مطلوب."
        )

        return redirect(
            url_for("admin_panel")
        )

    permissions = request.form.getlist(
        "permissions"
    )

    sections = request.form.getlist(
        "sections"
    )

    permissions = [
        p for p in permissions
        if p in PERMISSIONS
    ]

    sections = [
        s for s in sections
        if s in SECTION_KEYS
    ]

    db = get_db()

    role = db.execute("""
        SELECT *
        FROM custom_admin_roles
        WHERE id = ?
    """, (
        role_id,
    )).fetchone()

    if not role:

        db.close()

        flash(
            "الرتبة المخصصة غير موجودة."
        )

        return redirect(
            url_for("admin_panel")
        )

    db.execute("""
        UPDATE custom_admin_roles
        SET role_name = ?
        WHERE id = ?
    """, (
        role_name,
        role_id
    ))

    db.execute("""
        DELETE FROM custom_role_permissions
        WHERE role_id = ?
    """, (
        role_id,
    ))

    db.execute("""
        DELETE FROM custom_role_sections
        WHERE role_id = ?
    """, (
        role_id,
    ))

    for permission in set(permissions):

        db.execute("""
            INSERT OR IGNORE INTO
            custom_role_permissions
            (
                role_id,
                permission
            )
            VALUES (?, ?)
        """, (
            role_id,
            permission
        ))

    for section in set(sections):

        db.execute("""
            INSERT OR IGNORE INTO
            custom_role_sections
            (
                role_id,
                section
            )
            VALUES (?, ?)
        """, (
            role_id,
            section
        ))

    db.commit()
    db.close()

    log_action(
        f"تعديل الرتبة المخصصة: {role_name}"
    )

    flash(
        "تم تعديل الرتبة المخصصة."
    )

    return redirect(
        url_for("admin_panel")
    )


# =========================================================
# حذف رتبة مخصصة
# =========================================================

@app.route(
    "/admin/roles/<int:role_id>/delete",
    methods=["POST"]
)
def delete_custom_role(role_id):

    if not (
        has_permission("admins_remove")
        or has_permission("admins_manage")
    ):

        flash(
            "لا تملك صلاحية حذف الرتبة."
        )

        return redirect(
            url_for("admin_panel")
        )

    db = get_db()

    role = db.execute("""
        SELECT *
        FROM custom_admin_roles
        WHERE id = ?
    """, (
        role_id,
    )).fetchone()

    if not role:

        db.close()

        flash(
            "الرتبة غير موجودة."
        )

        return redirect(
            url_for("admin_panel")
        )

    db.execute("""
        UPDATE users
        SET role = 'helper'
        WHERE role = ?
    """, (
        role["role_key"],
    ))

    db.execute("""
        DELETE FROM custom_admin_roles
        WHERE id = ?
    """, (
        role_id,
    ))

    db.commit()
    db.close()

    log_action(
        f"حذف الرتبة المخصصة: "
        f"{role['role_name']}"
    )

    flash(
        f"تم حذف الرتبة {role['role_name']}."
    )

    return redirect(
        url_for("admin_panel")
    )


# =========================================================
# إعطاء رتبة مخصصة لمستخدم
# =========================================================

@app.route(
    "/admin/users/<int:user_id>/role",
    methods=["POST"]
)
def assign_user_role(user_id):

    if not (
        has_permission("admins_add")
        or has_permission("permissions_give")
        or has_permission("admins_manage")
    ):

        flash(
            "لا تملك صلاحية إعطاء رتبة."
        )

        return redirect(
            url_for("users")
        )

    role_key = request.form.get(
        "role",
        ""
    ).strip()

    db = get_db()

    target = db.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (
        user_id,
    )).fetchone()

    if not target:

        db.close()

        flash(
            "المستخدم غير موجود."
        )

        return redirect(
            url_for("users")
        )

    current = current_user()

    if (
        target["is_owner"]
        and not current["is_owner"]
    ):

        db.close()

        flash(
            "لا يمكنك تعديل Owner."
        )

        return redirect(
            url_for("users")
        )

    custom_role = db.execute("""
        SELECT *
        FROM custom_admin_roles
        WHERE role_key = ?
        LIMIT 1
    """, (
        role_key,
    )).fetchone()

    if (
        role_key not in ROLES
        and not custom_role
    ):

        db.close()

        flash(
            "الرتبة غير موجودة."
        )

        return redirect(
            url_for("users")
        )

    if (
        role_key == "owner"
        and not current["is_owner"]
    ):

        db.close()

        flash(
            "فقط Owner يستطيع تعيين Owner."
        )

        return redirect(
            url_for("users")
        )

    db.execute("""
        UPDATE users
        SET
            role = ?,
            is_owner = ?
        WHERE id = ?
    """, (
        role_key,
        1 if role_key == "owner" else 0,
        user_id
    ))

    db.commit()
    db.close()

    log_action(
        f"تعيين رتبة "
        f"{role_display_name(role_key)} "
        f"للمستخدم {target['username']}"
    )

    flash(
        f"تم تعيين رتبة "
        f"{role_display_name(role_key)} "
        f"للمستخدم {target['username']}."
    )

    return redirect(
        url_for("users")
    )


# =========================================================
# المستخدمون
# =========================================================

@app.route("/admin/users")
def users():

    if not (
        has_permission("users_view")
        or has_section_access("users")
        or has_permission("admins_manage")
    ):

        flash(
            "لا تملك صلاحية عرض المستخدمين."
        )

        return redirect(
            url_for("home")
        )

    db = get_db()

    users_list = db.execute("""
        SELECT
            id,
            username,
            is_banned,
            is_disabled,
            is_owner,
            role,
            created_at
        FROM users
        ORDER BY id DESC
    """).fetchall()

    custom_roles = db.execute("""
        SELECT *
        FROM custom_admin_roles
        ORDER BY role_name
    """).fetchall()

    db.close()

    user_roles = {}

    for account in users_list:

        user_roles[
            account["id"]
        ] = role_display_name(
            "owner"
            if account["is_owner"]
            else (
                account["role"]
                or "helper"
            )
        )

    all_roles = dict(ROLES)

    for role in custom_roles:

        all_roles[
            role["role_key"]
        ] = {
            "name": role["role_name"],
            "permissions": set()
        }

    return render_template(
        "users.html",
        users=users_list,
        user_roles=user_roles,
        ROLES=all_roles,
        custom_roles=custom_roles
    )


# =========================================================
# إضافة مستخدم
# =========================================================

@app.route(
    "/admin/users/add",
    methods=["POST"]
)
def add_user():

    if not (
        has_permission("admins_add")
        or has_permission("admins_manage")
    ):

        flash(
            "لا تملك صلاحية إضافة مستخدم."
        )

        return redirect(
            url_for("users")
        )

    username = request.form.get(
        "username",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    )

    role_key = request.form.get(
        "role",
        "helper"
    ).strip()

    if not username or not password:

        flash(
            "اسم المستخدم وكلمة المرور مطلوبة."
        )

        return redirect(
            url_for("users")
        )

    if len(username) < 3:

        flash(
            "اسم المستخدم يجب أن يكون 3 أحرف على الأقل."
        )

        return redirect(
            url_for("users")
        )

    if len(password) < 6:

        flash(
            "كلمة المرور يجب أن تكون 6 أحرف على الأقل."
        )

        return redirect(
            url_for("users")
        )

    db = get_db()

    custom_role = db.execute("""
        SELECT id
        FROM custom_admin_roles
        WHERE role_key = ?
        LIMIT 1
    """, (
        role_key,
    )).fetchone()

    if (
        role_key not in ROLES
        and not custom_role
    ):

        role_key = "helper"

    current = current_user()

    if (
        role_key == "owner"
        and not current["is_owner"]
    ):

        db.close()

        flash(
            "فقط Owner يستطيع إنشاء Owner."
        )

        return redirect(
            url_for("users")
        )

    exists = db.execute("""
        SELECT id
        FROM users
        WHERE username = ?
    """, (
        username,
    )).fetchone()

    if exists:

        db.close()

        flash(
            "اسم المستخدم موجود مسبقًا."
        )

        return redirect(
            url_for("users")
        )

    db.execute("""
        INSERT INTO users
        (
            username,
            password_hash,
            is_owner,
            role
        )
        VALUES (?, ?, ?, ?)
    """, (
        username,
        generate_password_hash(password),
        1 if role_key == "owner" else 0,
        role_key
    ))

    db.commit()
    db.close()

    log_action(
        f"إنشاء مستخدم: {username}"
    )

    flash(
        f"تم إنشاء المستخدم {username}."
    )

    return redirect(
        url_for("users")
    )


# =========================================================
# حظر المستخدم
# =========================================================

@app.route(
    "/admin/users/<int:user_id>/ban",
    methods=["POST"]
)
@permission_required(
    "users_ban"
)
def ban_user(user_id):

    db = get_db()

    user = db.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (
        user_id,
    )).fetchone()

    if user and user["is_owner"]:

        db.close()

        flash(
            "لا يمكن حظر مالك الموقع."
        )

        return redirect(
            url_for("users")
        )

    db.execute("""
        UPDATE users
        SET is_banned = 1
        WHERE id = ?
    """, (
        user_id,
    ))

    db.commit()
    db.close()

    log_action(
        f"حظر المستخدم رقم {user_id}"
    )

    flash(
        "تم حظر المستخدم."
    )

    return redirect(
        url_for("users")
    )


# =========================================================
# فك الحظر
# =========================================================

@app.route(
    "/admin/users/<int:user_id>/unban",
    methods=["POST"]
)
@permission_required(
    "users_unban"
)
def unban_user(user_id):

    db = get_db()

    db.execute("""
        UPDATE users
        SET is_banned = 0
        WHERE id = ?
    """, (
        user_id,
    ))

    db.commit()
    db.close()

    log_action(
        f"فك حظر المستخدم رقم {user_id}"
    )

    flash(
        "تم فك الحظر."
    )

    return redirect(
        url_for("users")
    )


# =========================================================
# تعطيل المستخدم
# =========================================================

@app.route(
    "/admin/users/<int:user_id>/disable",
    methods=["POST"]
)
@permission_required(
    "users_disable"
)
def disable_user(user_id):

    db = get_db()

    user = db.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (
        user_id,
    )).fetchone()

    if user and user["is_owner"]:

        db.close()

        flash(
            "لا يمكن تعطيل مالك الموقع."
        )

        return redirect(
            url_for("users")
        )

    db.execute("""
        UPDATE users
        SET is_disabled = 1
        WHERE id = ?
    """, (
        user_id,
    ))

    db.commit()
    db.close()

    log_action(
        f"تعطيل المستخدم رقم {user_id}"
    )

    flash(
        "تم تعطيل المستخدم."
    )

    return redirect(
        url_for("users")
    )


# =========================================================
# تفعيل المستخدم
# =========================================================

@app.route(
    "/admin/users/<int:user_id>/enable",
    methods=["POST"]
)
@permission_required(
    "users_enable"
)
def enable_user(user_id):

    db = get_db()

    db.execute("""
        UPDATE users
        SET is_disabled = 0
        WHERE id = ?
    """, (
        user_id,
    ))

    db.commit()
    db.close()

    log_action(
        f"تفعيل المستخدم رقم {user_id}"
    )

    flash(
        "تم تفعيل المستخدم."
    )

    return redirect(
        url_for("users")
    )


# =========================================================
# حذف المستخدم
# =========================================================

@app.route(
    "/admin/users/<int:user_id>/delete",
    methods=["POST"]
)
@permission_required(
    "users_delete"
)
def delete_user(user_id):

    db = get_db()

    user = db.execute("""
        SELECT *
        FROM users
        WHERE id = ?
    """, (
        user_id,
    )).fetchone()

    if user and user["is_owner"]:

        db.close()

        flash(
            "لا يمكن حذف مالك الموقع."
        )

        return redirect(
            url_for("users")
        )

    db.execute("""
        DELETE FROM users
        WHERE id = ?
    """, (
        user_id,
    ))

    db.commit()
    db.close()

    log_action(
        f"حذف المستخدم رقم {user_id}"
    )

    flash(
        "تم حذف المستخدم."
    )

    return redirect(
        url_for("users")
    )


# =========================================================
# السجلات
# =========================================================

@app.route("/admin/logs")
def logs():

    if not (
        has_permission("logs_view")
        or has_section_access("logs")
        or has_permission("admins_manage")
    ):

        flash(
            "لا تملك صلاحية عرض السجلات."
        )

        return redirect(
            url_for("home")
        )

    db = get_db()

    logs_list = db.execute("""
        SELECT
            activity_logs.id,
            activity_logs.action,
            activity_logs.details,
            activity_logs.created_at,
            users.username

        FROM activity_logs

        LEFT JOIN users
        ON users.id = activity_logs.user_id

        ORDER BY activity_logs.id DESC
    """).fetchall()

    db.close()

    return render_template(
        "logs.html",
        logs=logs_list
    )


# =========================================================
# تشغيل قاعدة البيانات
# =========================================================

init_db()
create_owner()


# =========================================================
# تشغيل الموقع
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        )
    )
