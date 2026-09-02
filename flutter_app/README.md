# Nagman Meter Reader - Flutter Android Client

Standalone Android client for configuring mechanical water meter layouts, capturing photos, and sending them to the Nagman OCR engine.

## Implemented in this first cut

- User-friendly 3-step meter configuration wizard.
- Pictographic meter preview.
- Dynamic rotary dial count.
- Drag each rotary dial to its physical position.
- Configure clockwise / anti-clockwise rotation per dial.
- Configure multiplier and engineering unit per dial.
- Configure counter digit count, decimal digits and multiplier.
- Configure meter/image orientation and layout type.
- Profiles saved locally and reusable.
- Rear camera capture and gallery import.
- Keep/discard/retake workflow.
- OCR request to the existing Flask `/process_realtime` endpoint.
- Reading result dialog with processing time and confidence when supplied by backend.
- Explicit warning rather than fabricated confidence when the existing backend does not provide confidence.

## Important current backend limitation

The Flutter profile JSON is sent with every OCR request, but the existing Flask endpoint currently ignores that profile and still contains fixed meter assumptions (`KERAS_INDICES`, `STRIP_INDEX`, `NUM_DIGITS`). The next backend milestone is to make `/api/v1/read` profile-aware and return per-component confidence.

## Android project generation

The execution environment used to prepare this branch did not contain a Flutter SDK, so platform scaffolding was not generated here. On a Flutter development machine, from `flutter_app` run:

```bash
flutter create --platforms=android .
flutter pub get
flutter run
```

Because `flutter create .` may regenerate `lib/main.dart`, preserve the `lib/` folder already committed on this branch if Flutter asks to overwrite files.

## Android permissions

Ensure `android/app/src/main/AndroidManifest.xml` contains:

```xml
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.INTERNET" />
```

For development against a plain `http://` Flask service on a local LAN, also set `android:usesCleartextTraffic="true"` on the `<application>` element. Production should use HTTPS or an embedded/on-device inference engine.

## OCR server address

The home page has an OCR Engine setting. Enter the LAN address of the PC running the Flask server, e.g.:

```text
http://192.168.1.20:5000
```

The phone and OCR PC must be reachable on the same network for this first version.

## Next milestone

1. Refactor Python inference into a profile-aware `/api/v1/read` endpoint.
2. Return confidence for each counter digit / rotary dial and an aggregate confidence.
3. Store captured images + result + profile/model version locally in Flutter.
4. Add operator correction and `Review Required` flow.
5. Benchmark the full Android-to-server round trip against the 5 second target.
6. Decide between LAN/local-server inference and an optimized on-device TFLite/ONNX runtime for deployment.
