// The window around the service.
//
// Order of events: start the packaged service as a sidecar (unless one is
// already answering — a second window must not become a second service),
// wait for the port, then send the webview to the interface. On exit the
// sidecar goes with the window: whoever closes the program means all of it.
//
// Closing the main window ends the whole program, and ending the program
// stops the service GENTLY (SIGTERM), so the service runs its own shutdown
// and takes its model, embedding, guardian and image-turbo servers down with
// it. The plugin's kill() is a hard SIGKILL that would skip that shutdown and
// leave those servers running — orphans that the next launch cannot talk to
// (a fresh session key, an old server: "Invalid API-Key"). SIGTERM first, a
// few seconds to bow out, then the hard kill only as a backstop.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::Manager;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

const PORT: u16 = 8090;

fn antwortet() -> bool {
    let adresse = std::net::SocketAddr::from(([127, 0, 0, 1], PORT));
    TcpStream::connect_timeout(&adresse, Duration::from_millis(400)).is_ok()
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let laeuft_schon = antwortet();
            let kind: Option<CommandChild> = if laeuft_schon {
                None
            } else {
                let (_ereignisse, kind) =
                    app.handle().shell().sidecar("exe-ai-terminal")?
                        .env("EXE_AI_TERMINAL_HEADLESS", "1")
                        .spawn()?;
                Some(kind)
            };
            app.manage(Mutex::new(kind));

            let fenster = app
                .get_webview_window("haupt")
                .expect("the window from the configuration");

            // Closing the main window means closing the program — on macOS a
            // window otherwise just hides and the service would keep running.
            let handle = app.handle().clone();
            fenster.on_window_event(move |ereignis| {
                if let tauri::WindowEvent::CloseRequested { .. } = ereignis {
                    handle.exit(0);
                }
            });

            // The splash page is showing; switch over as soon as the
            // service answers. Thirty seconds covers a first start that
            // still has a database to set up.
            let fenster_wechsel = fenster.clone();
            std::thread::spawn(move || {
                let ende = Instant::now() + Duration::from_secs(30);
                while Instant::now() < ende {
                    if antwortet() {
                        let _ = fenster_wechsel.eval(&format!(
                            "window.location.replace('http://127.0.0.1:{PORT}/app/')"
                        ));
                        return;
                    }
                    std::thread::sleep(Duration::from_millis(300));
                }
                let _ = fenster_wechsel.eval(
                    "document.body.dataset.zustand = 'fehlgeschlagen'",
                );
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("the shell itself")
        .run(|app, ereignis| {
            if let tauri::RunEvent::Exit = ereignis {
                if let Some(schloss) = app.try_state::<Mutex<Option<CommandChild>>>() {
                    if let Some(kind) = schloss.lock().unwrap().take() {
                        let pid = kind.pid();
                        // SIGTERM: let the service shut down and take its
                        // servers with it. Then wait for its port to fall
                        // silent — that means the shutdown ran — up to a few
                        // seconds, before the hard kill as a last resort.
                        unsafe {
                            libc::kill(pid as libc::pid_t, libc::SIGTERM);
                        }
                        let ende = Instant::now() + Duration::from_secs(10);
                        while Instant::now() < ende && antwortet() {
                            std::thread::sleep(Duration::from_millis(150));
                        }
                        let _ = kind.kill();
                    }
                }
            }
        });
}
