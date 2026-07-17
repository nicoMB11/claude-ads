from mb_rebuild import dbclean

# A tiny synthetic dump exercising each marker category.
CLEAN_DUMP = """
INSERT INTO `wp_options` VALUES (1,'siteurl','https://example.com','yes');
INSERT INTO `wp_options` VALUES (2,'blogname','My Site','yes');
INSERT INTO `wp_users` VALUES (1,'admin','$P$hash','admin','admin@example.com','...');
"""

DIRTY_DUMP = """
INSERT INTO `wp_options` VALUES (1,'siteurl','https://example.com','yes');
INSERT INTO `wp_options` VALUES (7,'wp_cache_hook','<?php eval(base64_decode("ZXZpbA==")); ?>','yes');
INSERT INTO `wp_options` VALUES (9,'cron','a:2:{i:123;}','yes');
INSERT INTO `wp_posts` VALUES (5,'Best online casino and viagra deals','<script>document.write("x")</script>');
INSERT INTO `wp_usermeta` VALUES (1,1,'session_tokens','...'),(2,1,'_application_passwords','...');
INSERT INTO `wp_users` VALUES (1,'admin','$P$hash','admin','admin@example.com','...');
INSERT INTO `wp_users` VALUES (2,'attacker','$P$hash','attacker','evil@bad.com','...');
"""


def test_clean_dump_has_no_findings():
    f = dbclean.scan_dump(CLEAN_DUMP, admin_whitelist=["admin"])
    assert not f.any()
    assert f.autoloaded_code == []
    assert f.injected_scripts == 0
    assert f.spam_posts == 0
    assert f.rogue_admins == []


def test_dirty_dump_detects_autoloaded_code():
    f = dbclean.scan_dump(DIRTY_DUMP, admin_whitelist=["admin"])
    assert "wp_cache_hook" in f.autoloaded_code
    assert f.cron_present is True


def test_dirty_dump_detects_scripts_and_spam():
    f = dbclean.scan_dump(DIRTY_DUMP)
    assert f.injected_scripts >= 1
    assert f.spam_posts >= 2  # casino + viagra


def test_dirty_dump_detects_application_passwords():
    f = dbclean.scan_dump(DIRTY_DUMP)
    assert f.application_passwords is True


def test_rogue_admin_flagged_against_whitelist():
    f = dbclean.scan_dump(DIRTY_DUMP, admin_whitelist=["admin"])
    assert "attacker" in f.rogue_admins
    assert "admin" not in f.rogue_admins


def test_no_whitelist_means_no_rogue_flag():
    f = dbclean.scan_dump(DIRTY_DUMP)
    assert f.rogue_admins == []


def test_report_hides_nothing_sensitive_and_lists_categories():
    f = dbclean.scan_dump(DIRTY_DUMP, admin_whitelist=["admin"])
    out = dbclean.report(f, dump_path="x.sql").render()
    assert "Autoloaded options with code" in out
    assert "Cron in wp_options" in out
    assert "Application passwords" in out
    assert "attacker" in out
