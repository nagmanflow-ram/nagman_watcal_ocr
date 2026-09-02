import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../models/meter_profile.dart';
import '../services/ocr_service.dart';

class CaptureScreen extends StatefulWidget {
  final MeterProfile profile;
  final String baseUrl;
  const CaptureScreen({super.key, required this.profile, required this.baseUrl});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  final _picker = ImagePicker();
  File? _image;
  bool _processing = false;

  Future<void> _pick(ImageSource source) async {
    final file = await _picker.pickImage(source: source, imageQuality: 92, preferredCameraDevice: CameraDevice.rear);
    if (file != null) setState(() => _image = File(file.path));
  }

  Future<void> _process() async {
    if (_image == null || _processing) return;
    setState(() => _processing = true);
    try {
      final result = await OcrService(widget.baseUrl).process(_image!, widget.profile);
      if (!mounted) return;
      await showDialog<void>(context: context, builder: (context) {
        final confidence = result.confidence == null ? 'Not reported' : '${(result.confidence! * 100).toStringAsFixed(1)}%';
        return AlertDialog(
          icon: Icon(result.confidence != null && result.confidence! < .80 ? Icons.warning_amber_rounded : Icons.check_circle, size: 42),
          title: const Text('Meter Reading'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            Text(result.reading, style: const TextStyle(fontSize: 36, fontWeight: FontWeight.w800)),
            Text(widget.profile.baseUnit, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 18),
            ListTile(contentPadding: EdgeInsets.zero, leading: const Icon(Icons.verified_outlined), title: const Text('Confidence'), trailing: Text(confidence, style: const TextStyle(fontWeight: FontWeight.bold))),
            ListTile(contentPadding: EdgeInsets.zero, leading: const Icon(Icons.timer_outlined), title: const Text('Processing time'), trailing: Text('${result.elapsed.inMilliseconds / 1000.0}s')),
            if (result.elapsed > const Duration(seconds: 5)) const Text('Processing exceeded the 5 second target.', style: TextStyle(color: Colors.orange)),
            ...result.warnings.map((e) => Padding(padding: const EdgeInsets.only(top: 8), child: Text(e, style: const TextStyle(color: Colors.orange)))),
          ]),
          actions: [
            TextButton(onPressed: () { Navigator.pop(context); setState(() => _image = null); }, child: const Text('Discard & Retake')),
            FilledButton(onPressed: () => Navigator.pop(context), child: const Text('Keep')),
          ],
        );
      });
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('OCR failed: $e')));
    } finally {
      if (mounted) setState(() => _processing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.profile.name)),
      body: SafeArea(child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(color: Theme.of(context).colorScheme.primaryContainer, borderRadius: BorderRadius.circular(16)),
          child: Row(children: [const Icon(Icons.tune), const SizedBox(width: 10), Expanded(child: Text('${widget.profile.counterDigits} counter digits • ${widget.profile.dials.length} dials • ${widget.profile.baseUnit}'))]),
        ),
        const SizedBox(height: 16),
        Expanded(child: Container(
          width: double.infinity,
          decoration: BoxDecoration(color: Colors.black87, borderRadius: BorderRadius.circular(22)),
          clipBehavior: Clip.antiAlias,
          child: _image == null
              ? const Center(child: Column(mainAxisSize: MainAxisSize.min, children: [Icon(Icons.photo_camera_outlined, size: 72, color: Colors.white54), SizedBox(height: 12), Text('Capture the complete meter face', style: TextStyle(color: Colors.white70))]))
              : Image.file(_image!, fit: BoxFit.contain),
        )),
        const SizedBox(height: 14),
        if (_image == null)
          Row(children: [Expanded(child: FilledButton.icon(onPressed: () => _pick(ImageSource.camera), icon: const Icon(Icons.camera_alt), label: const Padding(padding: EdgeInsets.all(14), child: Text('Take Photo')))), const SizedBox(width: 10), IconButton.filledTonal(onPressed: () => _pick(ImageSource.gallery), icon: const Icon(Icons.photo_library_outlined))])
        else
          Row(children: [Expanded(child: OutlinedButton.icon(onPressed: _processing ? null : () => setState(() => _image = null), icon: const Icon(Icons.delete_outline), label: const Text('Discard'))), const SizedBox(width: 10), Expanded(flex: 2, child: FilledButton.icon(onPressed: _processing ? null : _process, icon: _processing ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.document_scanner_outlined), label: Padding(padding: const EdgeInsets.all(14), child: Text(_processing ? 'Reading…' : 'Process OCR'))))]),
      ]))),
    );
  }
}
