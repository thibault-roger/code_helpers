# sales_orders.hcl
# Multi-table schema definition.
# Table and column names are block labels; schema/type may be bare identifiers.

table "sales_orders" {
  schema  = public
  comment = "Sales orders fact table"
  owner   = "data-team"

  column "order_id" {
    type    = integer
    null    = false
    comment = "Unique order identifier"
  }

  column "customer_id" {
    type    = integer
    null    = false
    comment = "Foreign key to the customers dimension table"
  }

  column "customer_name" {
    type    = varchar
    length  = 255
    null    = true
    comment = "Customer full name at time of order"
    tags    = ["pii"]
  }

  column "order_date" {
    type    = date
    null    = false
    comment = "Date the order was placed"
  }

  column "shipped_at" {
    type    = timestamp
    null    = true
    comment = "Timestamp when the order was shipped"
  }

  column "amount" {
    type      = decimal
    precision = 10
    scale     = 2
    null      = false
    comment   = "Total order amount excluding tax"
    tags      = ["finance"]
  }

  column "tax_amount" {
    type      = decimal
    precision = 10
    scale     = 2
    null      = true
    comment   = "Tax amount applied to the order"
    tags      = ["finance"]
  }

  column "status" {
    type    = varchar
    length  = 50
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

  column "notes" {
    type    = text
    null    = true
    comment = "Free-text notes added by customer service"
    tags    = ["free_text", "unstructured"]
  }

  primary_key {
    columns = [column.order_id]
  }
}

table "customers" {
  schema  = public
  comment = "Customer dimension table"
  owner   = "data-team"

  column "customer_id" {
    type    = integer
    null    = false
    comment = "Unique customer identifier"
  }

  column "full_name" {
    type    = varchar
    length  = 255
    null    = false
    comment = "Customer full name"
    tags    = ["pii"]
  }

  column "email" {
    type    = varchar
    length  = 320
    null    = true
    comment = "Contact email address"
    tags    = ["pii"]
  }

  column "created_at" {
    type    = timestamp
    null    = false
    comment = "Account creation timestamp"
  }

  primary_key {
    columns = [column.customer_id]
  }
}
