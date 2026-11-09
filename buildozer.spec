[app]
title = Sherlock
package.name = sherlock
package.domain = com.sherlock.app
source.dir = .
source.include_exts = py,png,jpg,kv,json
version = 1.0

# openssl is required for HTTPS requests on Android
requirements = python3,kivy,openssl,requests,certifi,charset_normalizer,idna,urllib3

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.api = 33
android.minapi = 21
android.archs = arm64-v8a

android.accept_sdk_license = True
android.logcat_filters = *:S python:D

[buildozer]
log_level = 2
warn_on_root = 1
