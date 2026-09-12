use std::collections::VecDeque;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use pyo3::prelude::*;
use serde_json::json;
use tokio::runtime::Runtime;
use tokio::sync::{broadcast, mpsc};

use crate::channel::{ChannelAction, ChannelDirection, ChannelMessage};
use crate::manager::SendInfo;
use crate::OutboundPayload;
use crate::{EndpointInfo, Visibility, RQS};

#[pyclass]
pub struct PyRQS {
    runtime: Arc<Runtime>,
    rqs: Arc<Mutex<Option<RQS>>>,
    sender_file: Arc<Mutex<Option<mpsc::Sender<SendInfo>>>>,
    dch_sender: broadcast::Sender<EndpointInfo>,
    message_queue: Arc<Mutex<VecDeque<String>>>,
    started: bool,
}

#[pymethods]
impl PyRQS {
    #[new]
    #[pyo3(signature = (visibility=None, port_number=None, download_path=None))]
    fn new(
        visibility: Option<u8>,
        port_number: Option<u32>,
        download_path: Option<String>,
    ) -> PyResult<Self> {
        let vis = visibility
            .map(|v| Visibility::from_raw_value(v as u64))
            .unwrap_or(Visibility::Visible);
        let path = download_path.map(PathBuf::from);

        let rqs = RQS::new(vis, port_number, path);
        let rt = Runtime::new().map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        let (dch_sender, _) = broadcast::channel(50);

        Ok(Self {
            runtime: Arc::new(rt),
            rqs: Arc::new(Mutex::new(Some(rqs))),
            sender_file: Arc::new(Mutex::new(None)),
            dch_sender,
            message_queue: Arc::new(Mutex::new(VecDeque::new())),
            started: false,
        })
    }

    fn start(&mut self) -> PyResult<()> {
        if self.started {
            return Ok(());
        }

        let rqs_arc = self.rqs.clone();
        let sender_file_arc = self.sender_file.clone();
        let message_queue = self.message_queue.clone();
        let dch_sender = self.dch_sender.clone();
        let rt = self.runtime.clone();

        rt.block_on(async move {
            let mut rqs_guard = rqs_arc.lock().unwrap();
            if let Some(ref mut rqs) = *rqs_guard {
                let message_sender = rqs.message_sender.clone();

                match rqs.run().await {
                    Ok((sender_file, _ble_receiver)) => {
                        *sender_file_arc.lock().unwrap() = Some(sender_file);

                        // Spawn message_sender receiver task
                        let mq1 = message_queue.clone();
                        let mut msg_rx = message_sender.subscribe();
                        tokio::spawn(async move {
                            loop {
                                match msg_rx.recv().await {
                                    Ok(msg) => {
                                        if msg.direction == ChannelDirection::FrontToLib {
                                            continue;
                                        }
                                        let payload = json!({
                                            "event": "rs2js_channelmessage",
                                            "payload": msg
                                        }).to_string();
                                        mq1.lock().unwrap().push_back(payload);
                                    }
                                    Err(broadcast::error::RecvError::Closed) => break,
                                    Err(_) => {}
                                }
                            }
                        });

                        // Spawn discovery endpoint receiver task
                        let mq2 = message_queue.clone();
                        let mut dch_rx = dch_sender.subscribe();
                        tokio::spawn(async move {
                            loop {
                                match dch_rx.recv().await {
                                    Ok(endpoint) => {
                                        let payload = json!({
                                            "event": "rs2js_endpointinfo",
                                            "payload": endpoint
                                        }).to_string();
                                        mq2.lock().unwrap().push_back(payload);
                                    }
                                    Err(broadcast::error::RecvError::Closed) => break,
                                    Err(_) => {}
                                }
                            }
                        });
                    }
                    Err(e) => {
                        error!("Failed to run RQS: {}", e);
                    }
                }
            }
        });

        self.started = true;
        Ok(())
    }

    fn start_discovery(&self) -> PyResult<()> {
        let rqs_arc = self.rqs.clone();
        let dch_sender = self.dch_sender.clone();
        let mut rqs_guard = rqs_arc.lock().unwrap();
        if let Some(ref mut rqs) = *rqs_guard {
            rqs.discovery(dch_sender)
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        }
        Ok(())
    }

    fn stop_discovery(&self) -> PyResult<()> {
        let rqs_arc = self.rqs.clone();
        let mut rqs_guard = rqs_arc.lock().unwrap();
        if let Some(ref mut rqs) = *rqs_guard {
            rqs.stop_discovery();
        }
        Ok(())
    }

    fn change_visibility(&self, visibility: u8) -> PyResult<()> {
        let rqs_arc = self.rqs.clone();
        let mut rqs_guard = rqs_arc.lock().unwrap();
        if let Some(ref mut rqs) = *rqs_guard {
            rqs.change_visibility(Visibility::from_raw_value(visibility as u64));
        }
        Ok(())
    }

    #[pyo3(signature = (download_path=None))]
    fn set_download_path(&self, download_path: Option<String>) -> PyResult<()> {
        let rqs_arc = self.rqs.clone();
        let rqs_guard = rqs_arc.lock().unwrap();
        if let Some(ref rqs) = *rqs_guard {
            rqs.set_download_path(download_path.map(PathBuf::from));
        }
        Ok(())
    }

    #[pyo3(signature = (id, name, addr, files=None))]
    fn send_payload(
        &self,
        id: String,
        name: String,
        addr: String,
        files: Option<Vec<String>>,
    ) -> PyResult<()> {
        let sender_file_opt = self.sender_file.lock().unwrap().clone();
        let sender_file = sender_file_opt
            .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("RQS not started"))?;

        let ob = OutboundPayload::Files(files.unwrap_or_default());
        let si = SendInfo { id, name, addr, ob };

        let rt = self.runtime.clone();
        rt.spawn(async move {
            let _ = sender_file.send(si).await;
        });

        Ok(())
    }

    fn send_action(&self, id: String, action_str: String) -> PyResult<()> {
        let action = match action_str.as_str() {
            "AcceptTransfer" => ChannelAction::AcceptTransfer,
            "RejectTransfer" => ChannelAction::RejectTransfer,
            "CancelTransfer" => ChannelAction::CancelTransfer,
            _ => {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "Unknown action: {}",
                    action_str
                )))
            }
        };

        let message = ChannelMessage {
            id,
            direction: ChannelDirection::FrontToLib,
            action: Some(action),
            rtype: None,
            state: None,
            meta: None,
        };

        let rqs_arc = self.rqs.clone();
        let rqs_guard = rqs_arc.lock().unwrap();
        if let Some(ref rqs) = *rqs_guard {
            let _ = rqs.message_sender.send(message);
        }

        Ok(())
    }

    fn poll_messages(&self) -> PyResult<Vec<String>> {
        let mut q = self.message_queue.lock().unwrap();
        let messages: Vec<String> = q.drain(..).collect();
        Ok(messages)
    }

    fn stop(&mut self) -> PyResult<()> {
        let rqs_arc = self.rqs.clone();
        let rt = self.runtime.clone();

        rt.block_on(async move {
            let mut rqs_guard = rqs_arc.lock().unwrap();
            if let Some(ref mut rqs) = *rqs_guard {
                rqs.stop().await;
            }
        });

        Ok(())
    }
}

#[pyfunction]
pub fn get_hostname() -> PyResult<String> {
    Ok(sys_metrics::host::get_hostname().unwrap_or_else(|_| "Unknown".to_string()))
}

#[pymodule]
pub fn rqs_lib(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyRQS>()?;
    m.add_function(wrap_pyfunction!(get_hostname, m)?)?;
    Ok(())
}
