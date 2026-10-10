-- Product Manager: database schema (Stage 1)
-- Tested on MariaDB 10.11 LTS. Not yet run on 11.8 LTS. The port is chosen by the client, not this file.
-- The app must connect in strict SQL mode (STRICT_TRANS_TABLES): in non-strict mode MariaDB
-- silently truncates over-long values instead of rejecting them.
--
-- WARNING: re-running this script DROPS both tables and recreates them empty.
--          All existing products and categories are lost. Run seed.sql afterwards
--          to reload the sample data.
--
-- Barcode policy (enforced in the database):
--   * stored as a string, so leading zeros are preserved
--   * digits only, 4 to 32 characters
--   * compared exactly (ascii_bin); the app trims whitespace before saving
-- Price:    DECIMAL(10,2), must be greater than 0 (no floating point)
-- Quantity: whole number, 0 allowed (out of stock), never negative

CREATE DATABASE IF NOT EXISTS shop_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE shop_db;
SET NAMES utf8mb4;

DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS categories;

CREATE TABLE categories (
    id   SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(100)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_categories_name (name),
    CONSTRAINT chk_categories_name CHECK (CHAR_LENGTH(TRIM(name)) > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE products (
    id          INT UNSIGNED      NOT NULL AUTO_INCREMENT,
    name        VARCHAR(150)      NOT NULL,
    barcode     VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    price       DECIMAL(10,2)     NOT NULL,
    quantity    INT               NOT NULL DEFAULT 0,
    category_id SMALLINT UNSIGNED NOT NULL,
    created_at  TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_products_barcode (barcode),
    KEY idx_products_name (name),
    KEY idx_products_category (category_id),
    CONSTRAINT fk_products_category
        FOREIGN KEY (category_id) REFERENCES categories (id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT chk_products_name     CHECK (CHAR_LENGTH(TRIM(name)) > 0),
    CONSTRAINT chk_products_barcode  CHECK (barcode REGEXP '^[0-9]{4,32}$'),
    CONSTRAINT chk_products_price    CHECK (price > 0),
    CONSTRAINT chk_products_quantity CHECK (quantity >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
