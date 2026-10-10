-- Product Manager: database schema and sample data (MariaDB)
-- Re-running this script recreates the database from scratch.

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS shop_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE shop_db;

DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS categories;

CREATE TABLE categories (
    id   INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_categories_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE products (
    id          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    name        VARCHAR(150)  NOT NULL,
    barcode     VARCHAR(50)   NOT NULL,
    price       DECIMAL(10,2) NOT NULL,
    quantity    INT UNSIGNED  NOT NULL,
    category_id INT UNSIGNED  NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_products_barcode (barcode),
    KEY idx_products_name (name),
    CONSTRAINT chk_products_price    CHECK (price > 0),
    CONSTRAINT chk_products_quantity CHECK (quantity > 0),
    CONSTRAINT fk_products_category
        FOREIGN KEY (category_id) REFERENCES categories (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO categories (name) VALUES
    ('مشروبات'),
    ('معلبات'),
    ('ألبان وأجبان'),
    ('حبوب وبقوليات'),
    ('منظفات');

INSERT INTO products (name, barcode, price, quantity, category_id) VALUES
    ('عصير برتقال 1 لتر',   '6221001000011',  4.50, 60, (SELECT id FROM categories WHERE name = 'مشروبات')),
    ('مياه معدنية 1.5 لتر', '6221001000028',  1.25, 200, (SELECT id FROM categories WHERE name = 'مشروبات')),
    ('شاي أسود 100 كيس',    '6221001000035',  7.75, 45, (SELECT id FROM categories WHERE name = 'مشروبات')),
    ('تونة معلبة 185 غ',    '6221001000042',  3.20, 120, (SELECT id FROM categories WHERE name = 'معلبات')),
    ('فول مدمس 400 غ',      '6221001000059',  1.90, 150, (SELECT id FROM categories WHERE name = 'معلبات')),
    ('حليب كامل الدسم 1 لتر','6221001000066', 2.40, 90, (SELECT id FROM categories WHERE name = 'ألبان وأجبان')),
    ('جبنة بيضاء 500 غ',    '6221001000073',  6.60, 35, (SELECT id FROM categories WHERE name = 'ألبان وأجبان')),
    ('أرز بسمتي 5 كغ',      '6221001000080', 18.00, 25, (SELECT id FROM categories WHERE name = 'حبوب وبقوليات')),
    ('عدس أحمر 1 كغ',       '6221001000097',  3.80, 70, (SELECT id FROM categories WHERE name = 'حبوب وبقوليات')),
    ('سائل جلي 750 مل',     '6221001000103',  4.95, 55, (SELECT id FROM categories WHERE name = 'منظفات'));
