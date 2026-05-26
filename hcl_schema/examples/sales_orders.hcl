# sales_orders.hcl
# Multi-table schema definition.
# Each labeled `table` block defines one table.

table "sales_orders" {
  description = "Sales orders fact table"
  database    = "analytics"
  schema      = "public"
  owner       = "data-team"

  column {
    name        = "order_id"
    type        = "INTEGER"
    nullable    = false
    primary_key = true
    description = "Unique order identifier"
  }

  column {
    name        = "customer_id"
    type        = "INTEGER"
    nullable    = false
    description = "Foreign key to the customers dimension table"
  }

  column {
    name        = "customer_name"
    type        = "VARCHAR"
    length      = 255
    nullable    = true
    description = "Customer full name at time of order"
    tags        = ["pii"]
  }

  column {
    name        = "order_date"
    type        = "DATE"
    nullable    = false
    description = "Date the order was placed"
  }

  column {
    name        = "shipped_at"
    type        = "TIMESTAMP"
    nullable    = true
    description = "Timestamp when the order was shipped"
  }

  column {
    name        = "amount"
    type        = "DECIMAL"
    precision   = 10
    scale       = 2
    nullable    = false
    description = "Total order amount excluding tax"
    tags        = ["finance"]
  }

  column {
    name        = "tax_amount"
    type        = "DECIMAL"
    precision   = 10
    scale       = 2
    nullable    = true
    description = "Tax amount applied to the order"
    tags        = ["finance"]
  }

  column {
    name        = "status"
    type        = "VARCHAR"
    length      = 50
    nullable    = false
    default     = "pending"
    description = "Order lifecycle status"
  }

  column {
    name        = "is_international"
    type        = "BOOLEAN"
    nullable    = false
    default     = false
    description = "True if the order ships outside the domestic market"
  }

  column {
    name        = "notes"
    type        = "TEXT"
    nullable    = true
    description = "Free-text notes added by customer service"
    tags        = ["free_text", "unstructured"]
  }
}

table "customers" {
  description = "Customer dimension table"
  database    = "analytics"
  schema      = "public"
  owner       = "data-team"

  column {
    name        = "customer_id"
    type        = "INTEGER"
    nullable    = false
    primary_key = true
    description = "Unique customer identifier"
  }

  column {
    name        = "full_name"
    type        = "VARCHAR"
    length      = 255
    nullable    = false
    description = "Customer full name"
    tags        = ["pii"]
  }

  column {
    name        = "email"
    type        = "VARCHAR"
    length      = 320
    nullable    = true
    description = "Contact email address"
    tags        = ["pii"]
  }

  column {
    name        = "created_at"
    type        = "TIMESTAMP"
    nullable    = false
    description = "Account creation timestamp"
  }
}
