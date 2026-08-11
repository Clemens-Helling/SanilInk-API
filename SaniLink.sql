CREATE TABLE "users" (
  "User_ID" integer PRIMARY KEY,
  "customer" integer,
  "name" varchar(255),
  "last_name" varchar(255),
  "teacher" integer,
  "departement" integer,
  "karten_nummer" varchar(255),
  "permission" varchar(255)
);

CREATE TABLE "user_settings" (
  "setting_id" integer PRIMARY KEY,
  "customer" integer,
  "notification_method" varchar(100),
  "notify_url" varchar(150),
  "dveria_key" varchar(250),
  "dveria_ric" varchar(150),
  "User_ID" integer
);

CREATE TABLE "teachers" (
  "teacher_id" integer PRIMARY KEY,
  "customer" integer,
  "first_name" varchar(255),
  "last_name" varchar(255),
  "house" varchar(255)
);

CREATE TABLE "departements" (
  "department_id" integer PRIMARY KEY,
  "customer" integer,
  "departement_name" varchar(255),
  "is_active" boolean,
  "location" int
);

CREATE TABLE "locations" (
  "location_id" integer PRIMARY KEY,
  "customer" integer,
  "name" varchar(255),
  "symbol" varchar(10),
  "is_active" bool
);

CREATE TABLE "alarmierungen" (
  "alert_id" integer PRIMARY KEY,
  "customer" integer,
  "alert_received" timestamp,
  "alert_type" varchar(255),
  "symptom" varchar(255)
);

CREATE TABLE "patient" (
  "id" integer PRIMARY KEY,
  "customer" integer,
  "real_name" text,
  "real_last_name" text,
  "birth_day" text,
  "created_at" timestamp,
  "pseudonym" varchar(255) UNIQUE
);

CREATE TABLE "protokolle" (
  "protokoll_id" integer PRIMARY KEY,
  "customer" integer,
  "alert_id" integer,
  "pseudonym" varchar(255),
  "teacher_id" integer,
  "operation_end" timestamp,
  "status" varchar(255),
  "pulse" integer,
  "spo2" integer,
  "blood_pressure" varchar(255),
  "temperature" integer,
  "blood_sugar" integer,
  "pain" varchar(255),
  "measures" text,
  "abhol_massnahme" varchar(255),
  "parents_notified_by" varchar(255),
  "parents_notified_at" timestamp,
  "hospital" varchar(255),
  "medic_id" integer
);

CREATE TABLE "sani_protokoll" (
  "sani_protokoll_id" integer PRIMARY KEY,
  "customer" integer,
  "sani1" integer,
  "sani2" integer,
  "operationsmanager" integer,
  "protokoll_id" integer
);

CREATE TABLE "materials" (
  "material_id" integer PRIMARY KEY,
  "customer" integer,
  "material_name" varchar(255),
  "material_barcode" varchar(255),
  "barcode_type" varchar(50),
  "quantity" integer,
  "expires_at" timestamp,
  "minimum_stock" integer
);

CREATE TABLE "protokoll_materials" (
  "material_protokoll_id" integer PRIMARY KEY,
  "customer" integer,
  "protokoll_id" integer,
  "material_id" integer,
  "quantity" integer
);

CREATE TABLE "customers" (
  "customer_id" int PRIMARY KEY,
  "customer_number" varchar(100) UNIQUE,
  "contact_person_first_name" varchar(255),
  "contact_person_last_name" varchar(255),
  "email" varchar(100),
  "phone_number" varchar(100)
);

CREATE TABLE "customer_key_slots" (
  "slot_id" integer PRIMARY KEY,
  "customer_id" integer,
  "user_id" integer,
  "encrypted_gek" text,
  "created_at" timestamp
);

CREATE TABLE "user_keys" (
  "key_id" integer PRIMARY KEY,
  "user_id" integer,
  "public_key" text,
  "encrypted_private_key" text,
  "argon2_salt" text,
  "created_at" timestamp,
  "is_active" boolean
);

ALTER TABLE "users" ADD FOREIGN KEY ("customer") REFERENCES "customers" ("customer_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "users" ADD FOREIGN KEY ("departement") REFERENCES "departements" ("department_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "user_settings" ADD FOREIGN KEY ("customer") REFERENCES "customers" ("customer_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "user_settings" ADD FOREIGN KEY ("User_ID") REFERENCES "users" ("User_ID") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "teachers" ADD FOREIGN KEY ("customer") REFERENCES "customers" ("customer_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "departements" ADD FOREIGN KEY ("customer") REFERENCES "customers" ("customer_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "departements" ADD FOREIGN KEY ("location") REFERENCES "locations" ("location_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "locations" ADD FOREIGN KEY ("customer") REFERENCES "customers" ("customer_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "alarmierungen" ADD FOREIGN KEY ("customer") REFERENCES "customers" ("customer_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "patient" ADD FOREIGN KEY ("customer") REFERENCES "customers" ("customer_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "protokolle" ADD FOREIGN KEY ("customer") REFERENCES "customers" ("customer_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "protokolle" ADD FOREIGN KEY ("alert_id") REFERENCES "alarmierungen" ("alert_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "protokolle" ADD FOREIGN KEY ("pseudonym") REFERENCES "patient" ("pseudonym") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "protokolle" ADD FOREIGN KEY ("teacher_id") REFERENCES "teachers" ("teacher_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "sani_protokoll" ADD FOREIGN KEY ("customer") REFERENCES "customers" ("customer_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "sani_protokoll" ADD FOREIGN KEY ("sani1") REFERENCES "users" ("User_ID") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "sani_protokoll" ADD FOREIGN KEY ("sani2") REFERENCES "users" ("User_ID") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "sani_protokoll" ADD FOREIGN KEY ("operationsmanager") REFERENCES "users" ("User_ID") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "sani_protokoll" ADD FOREIGN KEY ("protokoll_id") REFERENCES "protokolle" ("protokoll_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "materials" ADD FOREIGN KEY ("customer") REFERENCES "customers" ("customer_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "protokoll_materials" ADD FOREIGN KEY ("customer") REFERENCES "customers" ("customer_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "protokoll_materials" ADD FOREIGN KEY ("protokoll_id") REFERENCES "protokolle" ("protokoll_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "protokoll_materials" ADD FOREIGN KEY ("material_id") REFERENCES "materials" ("material_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "customer_key_slots" ADD FOREIGN KEY ("customer_id") REFERENCES "customers" ("customer_id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "customer_key_slots" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("User_ID") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "user_keys" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("User_ID") DEFERRABLE INITIALLY IMMEDIATE;
