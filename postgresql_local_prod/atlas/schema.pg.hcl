# schema.pg.hcl — desired state of the database (Atlas HCL, PostgreSQL dialect).
#
# This file is the single source of truth. You never write migration SQL by hand:
# edit this file, then run `make migrate-diff name=<what_changed>` and Atlas writes
# the next versioned migration into ./migrations by comparing this file with the
# migrations already there (using the empty ATLAS_DEV_URL database as a scratchpad).
#
# The same migrations/ folder is applied locally and in production.

schema "public" {
  comment = "standard public schema"
}

table "customers" {
  schema  = schema.public
  comment = "Customer dimension table"

  column "customer_id" {
    type    = integer
    null    = false
    comment = "Unique customer identifier"
  }
  column "full_name" {
    type    = varchar(255)
    null    = false
    comment = "Customer full name"
  }
  column "email" {
    type    = varchar(320)
    null    = true
    comment = "Contact email address"
  }
  column "created_at" {
    type    = timestamptz
    null    = false
    default = sql("now()")
    comment = "Account creation timestamp (UTC)"
  }

  primary_key {
    columns = [column.customer_id]
  }
  index "customers_email_key" {
    unique  = true
    columns = [column.email]
  }
}

table "sales_orders" {
  schema  = schema.public
  comment = "Sales orders fact table"

  column "order_id" {
    type    = bigint
    null    = false
    comment = "Unique order identifier"
  }
  column "customer_id" {
    type    = integer
    null    = false
    comment = "Foreign key to customers"
  }
  column "order_date" {
    type    = date
    null    = false
    comment = "Date the order was placed"
  }
  column "shipped_at" {
    type    = timestamptz
    null    = true
    comment = "Timestamp when the order was shipped (UTC)"
  }
  column "amount" {
    type    = numeric(10, 2)
    null    = false
    comment = "Total order amount excluding tax"
  }
  column "status" {
    type    = varchar(50)
    null    = false
    default = "pending"
    comment = "Order lifecycle status"
  }
  column "is_international" {
    type    = boolean
    null    = false
    default = false
    comment = "True if the order ships outside the domestic market"
  }

  primary_key {
    columns = [column.order_id]
  }
  foreign_key "sales_orders_customer_fk" {
    columns     = [column.customer_id]
    ref_columns = [table.customers.column.customer_id]
    on_delete   = RESTRICT
  }
  index "sales_orders_order_date_idx" {
    columns = [column.order_date]
  }
  check "sales_orders_amount_non_negative" {
    expr = "amount >= 0"
  }
}
