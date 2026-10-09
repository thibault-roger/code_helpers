-- Create "customers" table
CREATE TABLE "public"."customers" (
  "customer_id" integer NOT NULL,
  "full_name" character varying(255) NOT NULL,
  "email" character varying(320) NULL,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("customer_id")
);
-- Create index "customers_email_key" to table: "customers"
CREATE UNIQUE INDEX "customers_email_key" ON "public"."customers" ("email");
-- Set comment to table: "customers"
COMMENT ON TABLE "public"."customers" IS 'Customer dimension table';
-- Set comment to column: "customer_id" on table: "customers"
COMMENT ON COLUMN "public"."customers"."customer_id" IS 'Unique customer identifier';
-- Set comment to column: "full_name" on table: "customers"
COMMENT ON COLUMN "public"."customers"."full_name" IS 'Customer full name';
-- Set comment to column: "email" on table: "customers"
COMMENT ON COLUMN "public"."customers"."email" IS 'Contact email address';
-- Set comment to column: "created_at" on table: "customers"
COMMENT ON COLUMN "public"."customers"."created_at" IS 'Account creation timestamp (UTC)';
-- Create "sales_orders" table
CREATE TABLE "public"."sales_orders" (
  "order_id" bigint NOT NULL,
  "customer_id" integer NOT NULL,
  "order_date" date NOT NULL,
  "shipped_at" timestamptz NULL,
  "amount" numeric(10,2) NOT NULL,
  "status" character varying(50) NOT NULL DEFAULT 'pending',
  "is_international" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("order_id"),
  CONSTRAINT "sales_orders_customer_fk" FOREIGN KEY ("customer_id") REFERENCES "public"."customers" ("customer_id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "sales_orders_amount_non_negative" CHECK (amount >= (0)::numeric)
);
-- Create index "sales_orders_order_date_idx" to table: "sales_orders"
CREATE INDEX "sales_orders_order_date_idx" ON "public"."sales_orders" ("order_date");
-- Set comment to table: "sales_orders"
COMMENT ON TABLE "public"."sales_orders" IS 'Sales orders fact table';
-- Set comment to column: "order_id" on table: "sales_orders"
COMMENT ON COLUMN "public"."sales_orders"."order_id" IS 'Unique order identifier';
-- Set comment to column: "customer_id" on table: "sales_orders"
COMMENT ON COLUMN "public"."sales_orders"."customer_id" IS 'Foreign key to customers';
-- Set comment to column: "order_date" on table: "sales_orders"
COMMENT ON COLUMN "public"."sales_orders"."order_date" IS 'Date the order was placed';
-- Set comment to column: "shipped_at" on table: "sales_orders"
COMMENT ON COLUMN "public"."sales_orders"."shipped_at" IS 'Timestamp when the order was shipped (UTC)';
-- Set comment to column: "amount" on table: "sales_orders"
COMMENT ON COLUMN "public"."sales_orders"."amount" IS 'Total order amount excluding tax';
-- Set comment to column: "status" on table: "sales_orders"
COMMENT ON COLUMN "public"."sales_orders"."status" IS 'Order lifecycle status';
-- Set comment to column: "is_international" on table: "sales_orders"
COMMENT ON COLUMN "public"."sales_orders"."is_international" IS 'True if the order ships outside the domestic market';
