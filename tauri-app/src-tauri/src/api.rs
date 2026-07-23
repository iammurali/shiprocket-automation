//! Shiprocket + Shopify HTTP integrations (port of the Python threads).

use crate::config::{self, AppConfig};
use serde::Serialize;
use serde_json::Value;

#[derive(Debug, Clone, Serialize)]
pub struct OrderDetails {
    pub order_id: String,
    pub phone: String,
    pub items: String,
    pub address: String,
}

async fn auth_shiprocket(config: &mut AppConfig) -> Result<String, String> {
    let client = reqwest::Client::new();
    let resp = client
        .post("https://apiv2.shiprocket.in/v1/external/auth/login")
        .json(&serde_json::json!({"email": config.email, "password": config.password}))
        .send()
        .await
        .map_err(|e| format!("Auth request failed: {e}"))?;
    if !resp.status().is_success() {
        return Err(format!("Failed to login to Shiprocket ({})", resp.status()));
    }
    let body: Value = resp.json().await.map_err(|e| e.to_string())?;
    let token = body
        .get("token")
        .and_then(|t| t.as_str())
        .ok_or("No token in Shiprocket auth response")?
        .to_string();
    config.token = token.clone();
    let _ = config::save(config);
    Ok(token)
}

fn value_str(v: &Value, key: &str) -> String {
    match v.get(key) {
        Some(Value::String(s)) => s.clone(),
        Some(Value::Number(n)) => n.to_string(),
        _ => String::new(),
    }
}

pub async fn fetch_order(search_key: &str, search_type: &str) -> Result<OrderDetails, String> {
    let mut cfg = config::load();
    if cfg.email.is_empty() || cfg.password.is_empty() {
        return Err("Please configure Shiprocket settings first.".into());
    }

    let mut token = cfg.token.clone();
    if token.is_empty() {
        token = auth_shiprocket(&mut cfg).await?;
    }

    let client = reqwest::Client::new();
    let url = format!(
        "https://apiv2.shiprocket.in/v1/external/orders?search={}",
        search_key
    );

    let mut resp = client
        .get(&url)
        .bearer_auth(&token)
        .send()
        .await
        .map_err(|e| format!("Connection failed: {e}"))?;

    if resp.status() == reqwest::StatusCode::UNAUTHORIZED {
        token = auth_shiprocket(&mut cfg).await?;
        resp = client
            .get(&url)
            .bearer_auth(&token)
            .send()
            .await
            .map_err(|e| format!("Connection failed: {e}"))?;
    }

    if !resp.status().is_success() {
        return Err(format!("Failed to fetch: {}", resp.status()));
    }

    let data: Value = resp.json().await.map_err(|e| e.to_string())?;
    let empty = vec![];
    let data_list = data
        .get("data")
        .and_then(|d| d.as_array())
        .unwrap_or(&empty);

    let target_order: Option<&Value> = match search_type {
        "phone" => {
            let mut sorted: Vec<&Value> = data_list.iter().collect();
            sorted.sort_by_key(|o| std::cmp::Reverse(o.get("id").and_then(|i| i.as_i64()).unwrap_or(0)));
            sorted.first().copied()
        }
        _ => {
            let exact = data_list.iter().find(|o| {
                value_str(o, "channel_order_id") == search_key || value_str(o, "id") == search_key
            });
            exact.or_else(|| {
                data_list
                    .iter()
                    .find(|o| value_str(o, "channel_order_id").contains(search_key))
            })
        }
    };

    let order = target_order.ok_or(format!("No order found for {}", search_key))?;

    // Address assembly
    let fname = value_str(order, "customer_name");
    let addr1 = value_str(order, "customer_address");
    let addr2 = value_str(order, "customer_address_2");
    let city = value_str(order, "customer_city");
    let state = value_str(order, "customer_state");
    let pincode = value_str(order, "customer_pincode");
    let country = value_str(order, "customer_country");

    let mut lines = vec![fname];
    if !addr1.is_empty() {
        lines.push(addr1);
    }
    if !addr2.is_empty() {
        lines.push(addr2);
    }
    let loc_parts: Vec<String> = [city, state, pincode]
        .into_iter()
        .filter(|s| !s.is_empty())
        .collect();
    if !loc_parts.is_empty() {
        lines.push(loc_parts.join(", "));
    }
    if !country.is_empty() {
        lines.push(country);
    }

    // Phone with masked-value fallbacks
    let mut phone = value_str(order, "customer_phone");
    if phone.is_empty() || phone.to_lowercase().contains("xxxx") {
        for alt in ["billing_phone", "shipping_phone", "pickup_phone", "phone"] {
            let p = value_str(order, alt);
            if !p.is_empty() && !p.to_lowercase().contains("xxxx") {
                phone = p;
                break;
            }
        }
    }

    let items: Vec<String> = order
        .get("products")
        .and_then(|p| p.as_array())
        .map(|prods| {
            prods
                .iter()
                .map(|p| {
                    format!(
                        "{} x{}",
                        value_str(p, "name"),
                        p.get("quantity").map(|q| q.to_string()).unwrap_or_default()
                    )
                })
                .collect()
        })
        .unwrap_or_default();

    let order_id = {
        let coid = value_str(order, "channel_order_id");
        if coid.is_empty() {
            value_str(order, "id")
        } else {
            coid
        }
    };

    Ok(OrderDetails {
        order_id,
        phone,
        items: items.join(", "),
        address: lines.join("\n"),
    })
}

#[derive(Debug, Clone, Serialize)]
pub struct ShopifyReport {
    pub total: usize,
    pub updated: Vec<String>,
    pub failed: Vec<String>,
}

pub async fn update_shopify_notes(order_ids: Vec<String>) -> Result<ShopifyReport, String> {
    let cfg = config::load();
    let url = cfg.shopify_url.trim().to_string();
    let token = cfg.shopify_token.trim().to_string();
    if url.is_empty() || token.is_empty() {
        return Err("Please configure Shopify Store URL and Access Token in Settings.".into());
    }

    let base_url = {
        let u = if url.starts_with("http") {
            url
        } else {
            format!("https://{}", url)
        };
        u.trim_end_matches('/').to_string()
    };

    let client = reqwest::Client::new();
    let total = order_ids.len();
    let mut updated = Vec::new();
    let mut failed = Vec::new();

    for order_id in order_ids {
        let order_id = order_id.trim().to_string();
        if order_id.is_empty() {
            continue;
        }
        let result: Result<(), String> = async {
            let search_url = format!(
                "{}/admin/api/2023-10/orders.json?name={}&status=any",
                base_url, order_id
            );
            let resp = client
                .get(&search_url)
                .header("X-Shopify-Access-Token", &token)
                .send()
                .await
                .map_err(|e| e.to_string())?;
            if !resp.status().is_success() {
                return Err(format!("search failed: {}", resp.status()));
            }
            let body: Value = resp.json().await.map_err(|e| e.to_string())?;
            let empty = vec![];
            let orders = body
                .get("orders")
                .and_then(|o| o.as_array())
                .unwrap_or(&empty);

            let target = orders.iter().find(|o| {
                value_str(o, "order_number") == order_id
                    || value_str(o, "name") == order_id
                    || value_str(o, "name") == format!("#{}", order_id)
            });
            let target = target.ok_or("order not found in Shopify")?;

            let shopify_id = target
                .get("id")
                .and_then(|i| i.as_i64())
                .ok_or("no shopify id")?;
            let current_note = value_str(target, "note");

            if current_note.contains("Shipped Via ST courier") {
                return Ok(()); // already done
            }

            let today = chrono::Local::now().format("%d-%m-%Y").to_string();
            let comment = format!("Shipped Via ST courier {}", today);
            let new_note = format!("{}\n{}", current_note, comment)
                .trim()
                .to_string();

            let update_url = format!(
                "{}/admin/api/2023-10/orders/{}.json",
                base_url, shopify_id
            );
            let upd = client
                .put(&update_url)
                .header("X-Shopify-Access-Token", &token)
                .json(&serde_json::json!({"order": {"id": shopify_id, "note": new_note}}))
                .send()
                .await
                .map_err(|e| e.to_string())?;
            if !upd.status().is_success() {
                return Err(format!("update failed: {}", upd.status()));
            }
            Ok(())
        }
        .await;

        match result {
            Ok(()) => updated.push(order_id),
            Err(_) => failed.push(order_id),
        }
    }

    Ok(ShopifyReport {
        total,
        updated,
        failed,
    })
}
