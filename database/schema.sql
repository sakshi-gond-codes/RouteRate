-- =====================================================================
-- RouteRate - Voice Rate Deck Engine : MySQL schema (reference)
-- =====================================================================
-- The recommended way to create these tables is Django migrations:
--     python manage.py migrate        (setup.bat does this for you)
-- This file is the same DDL, generated with `manage.py sqlmigrate`, for
-- reviewing the design or creating the schema by hand.
-- Target: MySQL 8.0+ (or MariaDB 10.5+), utf8mb4.
--
-- Core tables
--   core_country             countries and ITU dial codes (prefix validation)
--   vendors_vendor           carriers we buy from
--   ratedecks_ratedeck       one uploaded file + processing statistics
--   ratedecks_ratedeckline   normalized, validated rates from a deck
--   ratedecks_deckissue      error report: errors, warnings, duplicates
--   ratedecks_decklog        step-by-step processing log
--   ratedecks_columnmapping  saved column mapping per vendor
--   ratedecks_vendorrate     LIVE routing table with effective_from / effective_to
--   routing_customer, routing_marginrule, routing_blockeddestination
--   routing_lcrrun, routing_lcrentry           saved Least Cost Routing results
--   routing_ratesheet, routing_ratesheetline   versioned customer price lists
--   core_activitylog         audit trail
-- =====================================================================

CREATE DATABASE IF NOT EXISTS routerate CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE routerate;

-- ---- contenttypes.0001_initial
CREATE TABLE `django_content_type` (`id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY, `name` varchar(100) NOT NULL, `app_label` varchar(100) NOT NULL, `model` varchar(100) NOT NULL);
ALTER TABLE `django_content_type` ADD CONSTRAINT `django_content_type_app_label_model_76bd3d3b_uniq` UNIQUE (`app_label`, `model`);

-- ---- contenttypes.0002_remove_content_type_name
-- (no-op)
ALTER TABLE `django_content_type` MODIFY `name` varchar(100) NULL;
-- THIS OPERATION CANNOT BE WRITTEN AS SQL
ALTER TABLE `django_content_type` DROP COLUMN `name`;

-- ---- auth.0001_initial
CREATE TABLE `auth_permission` (`id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY, `name` varchar(50) NOT NULL, `content_type_id` integer NOT NULL, `codename` varchar(100) NOT NULL);
CREATE TABLE `auth_group` (`id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY, `name` varchar(80) NOT NULL UNIQUE);
CREATE TABLE `auth_group_permissions` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `group_id` integer NOT NULL, `permission_id` integer NOT NULL);
-- (no-op)
ALTER TABLE `auth_permission` ADD CONSTRAINT `auth_permission_content_type_id_codename_01ab375a_uniq` UNIQUE (`content_type_id`, `codename`);
ALTER TABLE `auth_permission` ADD CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`);
ALTER TABLE `auth_group_permissions` ADD CONSTRAINT `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` UNIQUE (`group_id`, `permission_id`);
ALTER TABLE `auth_group_permissions` ADD CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`);
ALTER TABLE `auth_group_permissions` ADD CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`);

-- ---- auth.0002_alter_permission_name_max_length
ALTER TABLE `auth_permission` MODIFY `name` varchar(255) NOT NULL;

-- ---- auth.0003_alter_user_email_max_length
-- (no-op)

-- ---- auth.0004_alter_user_username_opts
-- (no-op)

-- ---- auth.0005_alter_user_last_login_null
-- (no-op)

-- ---- auth.0006_require_contenttypes_0002

-- ---- auth.0007_alter_validators_add_error_messages
-- (no-op)

-- ---- auth.0008_alter_user_username_max_length
-- (no-op)

-- ---- auth.0009_alter_user_last_name_max_length
-- (no-op)

-- ---- auth.0010_alter_group_name_max_length
ALTER TABLE `auth_group` MODIFY `name` varchar(150) NOT NULL;

-- ---- auth.0011_update_proxy_permissions
-- THIS OPERATION CANNOT BE WRITTEN AS SQL

-- ---- auth.0012_alter_user_first_name_max_length
-- (no-op)

-- ---- accounts.0001_initial
CREATE TABLE `accounts_user` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `password` varchar(128) NOT NULL, `last_login` datetime(6) NULL, `is_superuser` bool NOT NULL, `username` varchar(150) NOT NULL UNIQUE, `first_name` varchar(150) NOT NULL, `last_name` varchar(150) NOT NULL, `email` varchar(254) NOT NULL, `is_staff` bool NOT NULL, `is_active` bool NOT NULL, `date_joined` datetime(6) NOT NULL, `role` varchar(20) NOT NULL);
CREATE TABLE `accounts_user_groups` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `user_id` bigint NOT NULL, `group_id` integer NOT NULL);
CREATE TABLE `accounts_user_user_permissions` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `user_id` bigint NOT NULL, `permission_id` integer NOT NULL);
ALTER TABLE `accounts_user_groups` ADD CONSTRAINT `accounts_user_groups_user_id_group_id_59c0b32f_uniq` UNIQUE (`user_id`, `group_id`);
ALTER TABLE `accounts_user_groups` ADD CONSTRAINT `accounts_user_groups_user_id_52b62117_fk_accounts_user_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`);
ALTER TABLE `accounts_user_groups` ADD CONSTRAINT `accounts_user_groups_group_id_bd11a704_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`);
ALTER TABLE `accounts_user_user_permissions` ADD CONSTRAINT `accounts_user_user_permi_user_id_permission_id_2ab516c2_uniq` UNIQUE (`user_id`, `permission_id`);
ALTER TABLE `accounts_user_user_permissions` ADD CONSTRAINT `accounts_user_user_p_user_id_e4f0a161_fk_accounts_` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`);
ALTER TABLE `accounts_user_user_permissions` ADD CONSTRAINT `accounts_user_user_p_permission_id_113bb443_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`);

-- ---- admin.0001_initial
CREATE TABLE `django_admin_log` (`id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY, `action_time` datetime(6) NOT NULL, `object_id` longtext NULL, `object_repr` varchar(200) NOT NULL, `action_flag` smallint UNSIGNED NOT NULL CHECK (`action_flag` >= 0), `change_message` longtext NOT NULL, `content_type_id` integer NULL, `user_id` bigint NOT NULL);
ALTER TABLE `django_admin_log` ADD CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`);
ALTER TABLE `django_admin_log` ADD CONSTRAINT `django_admin_log_user_id_c564eba6_fk_accounts_user_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`);

-- ---- admin.0002_logentry_remove_auto_add
-- (no-op)

-- ---- admin.0003_logentry_add_action_flag_choices
-- (no-op)

-- ---- core.0001_initial
CREATE TABLE `core_country` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `name` varchar(80) NOT NULL UNIQUE, `iso_code` varchar(2) NOT NULL, `dial_code` varchar(6) NOT NULL UNIQUE, `region` varchar(40) NOT NULL, `aliases` varchar(200) NOT NULL);
CREATE TABLE `core_activitylog` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `action` varchar(30) NOT NULL, `description` varchar(300) NOT NULL, `created_at` datetime(6) NOT NULL, `user_id` bigint NULL);
ALTER TABLE `core_activitylog` ADD CONSTRAINT `core_activitylog_user_id_8705e516_fk_accounts_user_id` FOREIGN KEY (`user_id`) REFERENCES `accounts_user` (`id`);
CREATE INDEX `core_activitylog_created_at_0dcde50a` ON `core_activitylog` (`created_at`);

-- ---- vendors.0001_initial
CREATE TABLE `vendors_vendor` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `name` varchar(120) NOT NULL UNIQUE, `code` varchar(10) NOT NULL UNIQUE, `contact_name` varchar(120) NOT NULL, `contact_email` varchar(254) NOT NULL, `default_increment` varchar(10) NOT NULL, `priority` smallint UNSIGNED NOT NULL CHECK (`priority` >= 0), `is_active` bool NOT NULL, `notes` longtext NOT NULL, `created_at` datetime(6) NOT NULL, `last_deck_at` datetime(6) NULL);

-- ---- ratedecks.0001_initial
CREATE TABLE `ratedecks_columnmapping` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `columns` json NOT NULL, `header_row` integer UNSIGNED NOT NULL CHECK (`header_row` >= 0), `sheet_name` varchar(100) NOT NULL, `date_order` varchar(3) NOT NULL, `updated_at` datetime(6) NOT NULL, `vendor_id` bigint NOT NULL UNIQUE);
CREATE TABLE `ratedecks_ratedeck` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `file` varchar(100) NOT NULL, `original_filename` varchar(255) NOT NULL, `file_type` varchar(5) NOT NULL, `deck_type` varchar(10) NOT NULL, `default_effective_date` date NOT NULL, `effective_date` date NULL, `duplicate_policy` varchar(10) NOT NULL, `status` varchar(12) NOT NULL, `mapping` json NOT NULL, `notes` varchar(255) NOT NULL, `uploaded_at` datetime(6) NOT NULL, `processed_at` datetime(6) NULL, `activated_at` datetime(6) NULL, `total_rows` integer UNSIGNED NOT NULL CHECK (`total_rows` >= 0), `valid_rows` integer UNSIGNED NOT NULL CHECK (`valid_rows` >= 0), `error_rows` integer UNSIGNED NOT NULL CHECK (`error_rows` >= 0), `warning_count` integer UNSIGNED NOT NULL CHECK (`warning_count` >= 0), `duplicate_count` integer UNSIGNED NOT NULL CHECK (`duplicate_count` >= 0), `prefix_count` integer UNSIGNED NOT NULL CHECK (`prefix_count` >= 0), `expanded_count` integer UNSIGNED NOT NULL CHECK (`expanded_count` >= 0), `new_count` integer UNSIGNED NOT NULL CHECK (`new_count` >= 0), `increase_count` integer UNSIGNED NOT NULL CHECK (`increase_count` >= 0), `decrease_count` integer UNSIGNED NOT NULL CHECK (`decrease_count` >= 0), `unchanged_count` integer UNSIGNED NOT NULL CHECK (`unchanged_count` >= 0), `removed_count` integer UNSIGNED NOT NULL CHECK (`removed_count` >= 0), `processing_ms` integer UNSIGNED NOT NULL CHECK (`processing_ms` >= 0), `activated_by_id` bigint NULL, `uploaded_by_id` bigint NULL, `vendor_id` bigint NOT NULL);
CREATE TABLE `ratedecks_decklog` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `level` varchar(10) NOT NULL, `message` varchar(300) NOT NULL, `created_at` datetime(6) NOT NULL, `deck_id` bigint NOT NULL);
CREATE TABLE `ratedecks_deckissue` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `row_number` integer UNSIGNED NULL CHECK (`row_number` >= 0), `level` varchar(10) NOT NULL, `field` varchar(30) NOT NULL, `value` varchar(200) NOT NULL, `message` varchar(300) NOT NULL, `deck_id` bigint NOT NULL);
CREATE TABLE `ratedecks_ratedeckline` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `row_number` integer UNSIGNED NOT NULL CHECK (`row_number` >= 0), `prefix` varchar(15) NOT NULL, `destination` varchar(120) NOT NULL, `rate` numeric(12, 6) NOT NULL, `increment` varchar(10) NOT NULL, `effective_date` date NOT NULL, `change` varchar(10) NOT NULL, `previous_rate` numeric(12, 6) NULL, `country_id` bigint NULL, `deck_id` bigint NOT NULL);
CREATE TABLE `ratedecks_vendorrate` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `prefix` varchar(15) NOT NULL, `destination` varchar(120) NOT NULL, `rate` numeric(12, 6) NOT NULL, `increment` varchar(10) NOT NULL, `effective_from` date NOT NULL, `effective_to` date NULL, `change` varchar(10) NOT NULL, `previous_rate` numeric(12, 6) NULL, `country_id` bigint NULL, `deck_id` bigint NOT NULL, `vendor_id` bigint NOT NULL);
ALTER TABLE `ratedecks_columnmapping` ADD CONSTRAINT `ratedecks_columnmapping_vendor_id_1cb37ee1_fk_vendors_vendor_id` FOREIGN KEY (`vendor_id`) REFERENCES `vendors_vendor` (`id`);
ALTER TABLE `ratedecks_ratedeck` ADD CONSTRAINT `ratedecks_ratedeck_activated_by_id_fd48d5df_fk_accounts_user_id` FOREIGN KEY (`activated_by_id`) REFERENCES `accounts_user` (`id`);
ALTER TABLE `ratedecks_ratedeck` ADD CONSTRAINT `ratedecks_ratedeck_uploaded_by_id_0e3c76d5_fk_accounts_user_id` FOREIGN KEY (`uploaded_by_id`) REFERENCES `accounts_user` (`id`);
ALTER TABLE `ratedecks_ratedeck` ADD CONSTRAINT `ratedecks_ratedeck_vendor_id_47f85d6e_fk_vendors_vendor_id` FOREIGN KEY (`vendor_id`) REFERENCES `vendors_vendor` (`id`);
CREATE INDEX `ratedecks_ratedeck_status_f99e3ad5` ON `ratedecks_ratedeck` (`status`);
CREATE INDEX `ratedecks_ratedeck_uploaded_at_6ab5f71a` ON `ratedecks_ratedeck` (`uploaded_at`);
ALTER TABLE `ratedecks_decklog` ADD CONSTRAINT `ratedecks_decklog_deck_id_8a4959dc_fk_ratedecks_ratedeck_id` FOREIGN KEY (`deck_id`) REFERENCES `ratedecks_ratedeck` (`id`);
ALTER TABLE `ratedecks_deckissue` ADD CONSTRAINT `ratedecks_deckissue_deck_id_7c1b0ecb_fk_ratedecks_ratedeck_id` FOREIGN KEY (`deck_id`) REFERENCES `ratedecks_ratedeck` (`id`);
CREATE INDEX `ratedecks_deckissue_level_e9dc4c0a` ON `ratedecks_deckissue` (`level`);
ALTER TABLE `ratedecks_ratedeckline` ADD CONSTRAINT `ratedecks_ratedeckline_country_id_4797373c_fk_core_country_id` FOREIGN KEY (`country_id`) REFERENCES `core_country` (`id`);
ALTER TABLE `ratedecks_ratedeckline` ADD CONSTRAINT `ratedecks_ratedeckline_deck_id_92bab5ea_fk_ratedecks_ratedeck_id` FOREIGN KEY (`deck_id`) REFERENCES `ratedecks_ratedeck` (`id`);
CREATE INDEX `ratedecks_r_deck_id_56763d_idx` ON `ratedecks_ratedeckline` (`deck_id`, `prefix`);
ALTER TABLE `ratedecks_vendorrate` ADD CONSTRAINT `ratedecks_vendorrate_country_id_e0de7002_fk_core_country_id` FOREIGN KEY (`country_id`) REFERENCES `core_country` (`id`);
ALTER TABLE `ratedecks_vendorrate` ADD CONSTRAINT `ratedecks_vendorrate_deck_id_4f4af678_fk_ratedecks_ratedeck_id` FOREIGN KEY (`deck_id`) REFERENCES `ratedecks_ratedeck` (`id`);
ALTER TABLE `ratedecks_vendorrate` ADD CONSTRAINT `ratedecks_vendorrate_vendor_id_3a50f646_fk_vendors_vendor_id` FOREIGN KEY (`vendor_id`) REFERENCES `vendors_vendor` (`id`);
CREATE INDEX `ratedecks_v_vendor__34b824_idx` ON `ratedecks_vendorrate` (`vendor_id`, `prefix`);
CREATE INDEX `ratedecks_v_prefix_51208b_idx` ON `ratedecks_vendorrate` (`prefix`);
CREATE INDEX `ratedecks_v_effecti_417c7f_idx` ON `ratedecks_vendorrate` (`effective_from`, `effective_to`);

-- ---- routing.0001_initial
CREATE TABLE `routing_customer` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `name` varchar(120) NOT NULL UNIQUE, `code` varchar(10) NOT NULL UNIQUE, `contact_email` varchar(254) NOT NULL, `billing_increment` varchar(10) NOT NULL, `notice_days` smallint UNSIGNED NOT NULL CHECK (`notice_days` >= 0), `rate_decimals` smallint UNSIGNED NOT NULL CHECK (`rate_decimals` >= 0), `is_active` bool NOT NULL, `notes` longtext NOT NULL, `created_at` datetime(6) NOT NULL);
CREATE TABLE `routing_blockeddestination` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `prefix` varchar(15) NOT NULL, `reason` varchar(200) NOT NULL, `is_active` bool NOT NULL, `created_at` datetime(6) NOT NULL, `created_by_id` bigint NULL, `vendor_id` bigint NULL);
CREATE TABLE `routing_lcrrun` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `as_of_date` date NOT NULL, `created_at` datetime(6) NOT NULL, `notes` varchar(200) NOT NULL, `vendor_count` integer UNSIGNED NOT NULL CHECK (`vendor_count` >= 0), `prefix_count` integer UNSIGNED NOT NULL CHECK (`prefix_count` >= 0), `routed_count` integer UNSIGNED NOT NULL CHECK (`routed_count` >= 0), `single_route_count` integer UNSIGNED NOT NULL CHECK (`single_route_count` >= 0), `no_route_count` integer UNSIGNED NOT NULL CHECK (`no_route_count` >= 0), `blocked_count` integer UNSIGNED NOT NULL CHECK (`blocked_count` >= 0), `avg_primary_rate` numeric(12, 6) NULL, `duration_ms` integer UNSIGNED NOT NULL CHECK (`duration_ms` >= 0), `created_by_id` bigint NULL);
CREATE TABLE `routing_marginrule` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `name` varchar(120) NOT NULL, `prefix` varchar(15) NOT NULL, `kind` varchar(10) NOT NULL, `value` numeric(10, 4) NOT NULL, `min_margin` numeric(10, 6) NOT NULL, `is_active` bool NOT NULL, `created_at` datetime(6) NOT NULL, `country_id` bigint NULL, `customer_id` bigint NULL);
CREATE TABLE `routing_ratesheet` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `version` integer UNSIGNED NOT NULL CHECK (`version` >= 0), `reference` varchar(40) NOT NULL UNIQUE, `effective_date` date NOT NULL, `created_at` datetime(6) NOT NULL, `notes` varchar(255) NOT NULL, `line_count` integer UNSIGNED NOT NULL CHECK (`line_count` >= 0), `new_count` integer UNSIGNED NOT NULL CHECK (`new_count` >= 0), `increase_count` integer UNSIGNED NOT NULL CHECK (`increase_count` >= 0), `decrease_count` integer UNSIGNED NOT NULL CHECK (`decrease_count` >= 0), `unchanged_count` integer UNSIGNED NOT NULL CHECK (`unchanged_count` >= 0), `removed_count` integer UNSIGNED NOT NULL CHECK (`removed_count` >= 0), `notice_adjusted_count` integer UNSIGNED NOT NULL CHECK (`notice_adjusted_count` >= 0), `avg_cost` numeric(12, 6) NULL, `avg_sell` numeric(12, 6) NULL, `avg_margin_pct` numeric(7, 2) NULL, `created_by_id` bigint NULL, `customer_id` bigint NOT NULL, `lcr_run_id` bigint NULL);
CREATE TABLE `routing_lcrentry` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `prefix` varchar(15) NOT NULL, `destination` varchar(120) NOT NULL, `status` varchar(10) NOT NULL, `vendor_count` smallint UNSIGNED NOT NULL CHECK (`vendor_count` >= 0), `primary_rate` numeric(12, 6) NULL, `primary_via` varchar(15) NOT NULL, `backup_rate` numeric(12, 6) NULL, `backup_via` varchar(15) NOT NULL, `third_rate` numeric(12, 6) NULL, `note` varchar(200) NOT NULL, `backup_vendor_id` bigint NULL, `country_id` bigint NULL, `primary_vendor_id` bigint NULL, `third_vendor_id` bigint NULL, `run_id` bigint NOT NULL);
CREATE TABLE `routing_ratesheetline` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `prefix` varchar(15) NOT NULL, `destination` varchar(120) NOT NULL, `rate` numeric(12, 6) NOT NULL, `previous_rate` numeric(12, 6) NULL, `cost` numeric(12, 6) NULL, `increment` varchar(10) NOT NULL, `effective_date` date NOT NULL, `change` varchar(10) NOT NULL, `notice_applied` bool NOT NULL, `backup_vendor_id` bigint NULL, `country_id` bigint NULL, `margin_rule_id` bigint NULL, `sheet_id` bigint NOT NULL, `vendor_id` bigint NULL);
ALTER TABLE `routing_blockeddestination` ADD CONSTRAINT `routing_blockeddesti_created_by_id_b8d6d1ca_fk_accounts_` FOREIGN KEY (`created_by_id`) REFERENCES `accounts_user` (`id`);
ALTER TABLE `routing_blockeddestination` ADD CONSTRAINT `routing_blockeddesti_vendor_id_c8ba0b52_fk_vendors_v` FOREIGN KEY (`vendor_id`) REFERENCES `vendors_vendor` (`id`);
ALTER TABLE `routing_lcrrun` ADD CONSTRAINT `routing_lcrrun_created_by_id_31b5cb60_fk_accounts_user_id` FOREIGN KEY (`created_by_id`) REFERENCES `accounts_user` (`id`);
ALTER TABLE `routing_marginrule` ADD CONSTRAINT `routing_marginrule_country_id_491a4549_fk_core_country_id` FOREIGN KEY (`country_id`) REFERENCES `core_country` (`id`);
ALTER TABLE `routing_marginrule` ADD CONSTRAINT `routing_marginrule_customer_id_6b9416a2_fk_routing_customer_id` FOREIGN KEY (`customer_id`) REFERENCES `routing_customer` (`id`);
ALTER TABLE `routing_ratesheet` ADD CONSTRAINT `routing_ratesheet_customer_id_version_11a20030_uniq` UNIQUE (`customer_id`, `version`);
ALTER TABLE `routing_ratesheet` ADD CONSTRAINT `routing_ratesheet_created_by_id_e996e0fd_fk_accounts_user_id` FOREIGN KEY (`created_by_id`) REFERENCES `accounts_user` (`id`);
ALTER TABLE `routing_ratesheet` ADD CONSTRAINT `routing_ratesheet_customer_id_c78d0cb1_fk_routing_customer_id` FOREIGN KEY (`customer_id`) REFERENCES `routing_customer` (`id`);
ALTER TABLE `routing_ratesheet` ADD CONSTRAINT `routing_ratesheet_lcr_run_id_5ec7b09a_fk_routing_lcrrun_id` FOREIGN KEY (`lcr_run_id`) REFERENCES `routing_lcrrun` (`id`);
ALTER TABLE `routing_lcrentry` ADD CONSTRAINT `routing_lcrentry_backup_vendor_id_381e94ec_fk_vendors_vendor_id` FOREIGN KEY (`backup_vendor_id`) REFERENCES `vendors_vendor` (`id`);
ALTER TABLE `routing_lcrentry` ADD CONSTRAINT `routing_lcrentry_country_id_6dbc251b_fk_core_country_id` FOREIGN KEY (`country_id`) REFERENCES `core_country` (`id`);
ALTER TABLE `routing_lcrentry` ADD CONSTRAINT `routing_lcrentry_primary_vendor_id_e8359e52_fk_vendors_vendor_id` FOREIGN KEY (`primary_vendor_id`) REFERENCES `vendors_vendor` (`id`);
ALTER TABLE `routing_lcrentry` ADD CONSTRAINT `routing_lcrentry_third_vendor_id_82eb76bb_fk_vendors_vendor_id` FOREIGN KEY (`third_vendor_id`) REFERENCES `vendors_vendor` (`id`);
ALTER TABLE `routing_lcrentry` ADD CONSTRAINT `routing_lcrentry_run_id_3ff57c6b_fk_routing_lcrrun_id` FOREIGN KEY (`run_id`) REFERENCES `routing_lcrrun` (`id`);
CREATE INDEX `routing_lcr_run_id_850107_idx` ON `routing_lcrentry` (`run_id`, `prefix`);
CREATE INDEX `routing_lcr_run_id_80ff90_idx` ON `routing_lcrentry` (`run_id`, `status`);
ALTER TABLE `routing_ratesheetline` ADD CONSTRAINT `routing_ratesheetlin_backup_vendor_id_a36f2fda_fk_vendors_v` FOREIGN KEY (`backup_vendor_id`) REFERENCES `vendors_vendor` (`id`);
ALTER TABLE `routing_ratesheetline` ADD CONSTRAINT `routing_ratesheetline_country_id_37fbf3fb_fk_core_country_id` FOREIGN KEY (`country_id`) REFERENCES `core_country` (`id`);
ALTER TABLE `routing_ratesheetline` ADD CONSTRAINT `routing_ratesheetlin_margin_rule_id_ebdb7a32_fk_routing_m` FOREIGN KEY (`margin_rule_id`) REFERENCES `routing_marginrule` (`id`);
ALTER TABLE `routing_ratesheetline` ADD CONSTRAINT `routing_ratesheetline_sheet_id_1b188afb_fk_routing_ratesheet_id` FOREIGN KEY (`sheet_id`) REFERENCES `routing_ratesheet` (`id`);
ALTER TABLE `routing_ratesheetline` ADD CONSTRAINT `routing_ratesheetline_vendor_id_d99fda3e_fk_vendors_vendor_id` FOREIGN KEY (`vendor_id`) REFERENCES `vendors_vendor` (`id`);
CREATE INDEX `routing_rat_sheet_i_38ceed_idx` ON `routing_ratesheetline` (`sheet_id`, `prefix`);

-- ---- sessions.0001_initial
CREATE TABLE `django_session` (`session_key` varchar(40) NOT NULL PRIMARY KEY, `session_data` longtext NOT NULL, `expire_date` datetime(6) NOT NULL);
CREATE INDEX `django_session_expire_date_a5c62663` ON `django_session` (`expire_date`);
