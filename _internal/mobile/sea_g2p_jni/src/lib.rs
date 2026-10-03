//! JNI entry points of sea-g2p for `vn.abook.player.vieneu.SeaG2pNative` (Kotlin). The three calls the desktop's
//! `vieneu_engine.phonemize` makes - `Normalizer.normalize`, `punc_norm`, `G2P.convert` - with nothing added: same crate,
//! same dictionary file, so the phone gets the desktop's phoneme strings byte for byte.
//!
//! A handle owns one G2P engine (memory-mapped dictionary); the normaliser's dictionary is a process-wide map that the
//! crate loads once (`init_norm_dict`). A panic inside the crate becomes an `IllegalStateException`, never a crash.

use jni::objects::{JClass, JString};
use jni::sys::{jboolean, jlong, jstring, JNI_FALSE};
use jni::JNIEnv;
use sea_g2p_rs::g2p::G2PEngine;
use sea_g2p_rs::lang::vi::Normalizer;
use std::panic::{catch_unwind, AssertUnwindSafe};

struct Engine {
    g2p: G2PEngine,
    normalizer: Normalizer,
}

fn fail(env: &mut JNIEnv, message: &str) {
    let _ = env.throw_new("java/lang/IllegalStateException", message);
}

fn text(env: &mut JNIEnv, value: &JString) -> Option<String> {
    match env.get_string(value) {
        Ok(chars) => Some(chars.into()),
        Err(_) => None,
    }
}

/// Run `body` with the Java string decoded; any panic or JNI failure turns into a Java exception and a null result.
fn with_text(env: &mut JNIEnv, value: &JString, body: impl FnOnce(&str) -> String) -> jstring {
    let Some(input) = text(env, value) else {
        fail(env, "sea-g2p: bad string");
        return std::ptr::null_mut();
    };
    match catch_unwind(AssertUnwindSafe(|| body(&input))) {
        Ok(out) => match env.new_string(out) {
            Ok(made) => made.into_raw(),
            Err(_) => std::ptr::null_mut(),
        },
        Err(_) => {
            fail(env, "sea-g2p panicked");
            std::ptr::null_mut()
        }
    }
}

fn engine<'a>(handle: jlong) -> &'a Engine {
    // SAFETY: the handle comes from nativeOpen and is closed only by nativeClose (SeaG2p never uses it afterwards).
    unsafe { &*(handle as *const Engine) }
}

#[no_mangle]
pub extern "system" fn Java_vn_abook_player_vieneu_SeaG2pNative_nativeOpen(mut env: JNIEnv, _class: JClass, path: JString) -> jlong {
    let Some(path) = text(&mut env, &path) else {
        fail(&mut env, "sea-g2p: bad path");
        return 0;
    };
    let opened = catch_unwind(AssertUnwindSafe(|| {
        G2PEngine::new(&path).map(|g2p| Engine { g2p, normalizer: Normalizer::new("vi", Some(&path)) })
    }));
    match opened {
        Ok(Ok(made)) => Box::into_raw(Box::new(made)) as jlong,
        Ok(Err(error)) => {
            fail(&mut env, &format!("sea-g2p: cannot open the dictionary ({error})"));
            0
        }
        Err(_) => {
            fail(&mut env, "sea-g2p panicked while opening the dictionary");
            0
        }
    }
}

#[no_mangle]
pub extern "system" fn Java_vn_abook_player_vieneu_SeaG2pNative_nativeClose(_env: JNIEnv, _class: JClass, handle: jlong) {
    if handle != 0 {
        // SAFETY: see `engine`; called once per handle.
        drop(unsafe { Box::from_raw(handle as *mut Engine) });
    }
}

#[no_mangle]
pub extern "system" fn Java_vn_abook_player_vieneu_SeaG2pNative_nativeNormalize(
    mut env: JNIEnv,
    _class: JClass,
    handle: jlong,
    value: JString,
    punc_norm: jboolean,
) -> jstring {
    let engine = engine(handle);
    with_text(&mut env, &value, |input| engine.normalizer.normalize(input, punc_norm != JNI_FALSE))
}

#[no_mangle]
pub extern "system" fn Java_vn_abook_player_vieneu_SeaG2pNative_nativePhonemize(mut env: JNIEnv, _class: JClass, handle: jlong, value: JString) -> jstring {
    let engine = engine(handle);
    with_text(&mut env, &value, |input| engine.g2p.phonemize(input))
}

#[no_mangle]
pub extern "system" fn Java_vn_abook_player_vieneu_SeaG2pNative_nativePuncNorm(mut env: JNIEnv, _class: JClass, value: JString) -> jstring {
    with_text(&mut env, &value, sea_g2p_rs::punc::apply_punc_norm)
}
