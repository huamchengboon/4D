//! PyO3 extension: fetch many past-result pages in parallel.
//! Returns list of (date, html) for Python.

use pyo3::prelude::*;
use std::sync::Arc;
use std::time::Duration;

const USER_AGENT: &str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
const TIMEOUT_SECS: u64 = 15;

async fn fetch_one(
    client: &reqwest::Client,
    base_url: &str,
    date_str: &str,
) -> (String, Option<String>) {
    let url = format!("{}/past-results", base_url.trim_end_matches('/'));
    let resp = client
        .post(&url)
        .form(&[("datepicker", date_str)])
        .send()
        .await;
    match resp {
        Ok(r) => match r.text().await {
            Ok(html) => (date_str.to_string(), Some(html)),
            Err(_) => (date_str.to_string(), None),
        },
        Err(_) => (date_str.to_string(), None),
    }
}

async fn fetch_all(base_url: String, dates: Vec<String>) -> Vec<(String, Option<String>)> {
    let client = reqwest::Client::builder()
        .user_agent(USER_AGENT)
        .timeout(Duration::from_secs(TIMEOUT_SECS))
        .build()
        .expect("reqwest client");
    let client = Arc::new(client);
    let mut handles = Vec::with_capacity(dates.len());
    for date_str in dates {
        let client = Arc::clone(&client);
        let base = base_url.clone();
        handles.push(tokio::spawn(async move {
            fetch_one(&client, &base, &date_str).await
        }));
    }
    let mut out = Vec::with_capacity(handles.len());
    for h in handles {
        if let Ok((d, html)) = h.await {
            out.push((d, html));
        }
    }
    out
}

/// Fetch past results HTML for multiple dates in parallel.
/// Returns a list of (date_str, html) tuples. html is None on fetch error.
#[pyfunction]
fn fetch_past_dates(
    base_url: &str,
    dates: Vec<String>,
) -> PyResult<Vec<(String, Option<String>)>> {
    if dates.is_empty() {
        return Ok(vec![]);
    }
    let rt = tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
    let out = rt.block_on(fetch_all(base_url.to_string(), dates));
    Ok(out)
}

#[pymodule]
fn fetch_4d(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(pyo3::wrap_pyfunction!(fetch_past_dates, m)?)?;
    Ok(())
}
