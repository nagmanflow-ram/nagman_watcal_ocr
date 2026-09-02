import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import '../models/meter_profile.dart';
import '../models/ocr_result.dart';

class OcrService {
  final String baseUrl;
  const OcrService(this.baseUrl);

  Future<OcrResult> process(File image, MeterProfile profile) async {
    final sw = Stopwatch()..start();
    final uri = Uri.parse('$baseUrl/process_realtime');
    final request = http.MultipartRequest('POST', uri)
      ..files.add(await http.MultipartFile.fromPath('image', image.path))
      ..fields['profile'] = jsonEncode(profile.toJson());
    final streamed = await request.send().timeout(const Duration(seconds: 8));
    final response = await http.Response.fromStream(streamed);
    sw.stop();

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('OCR server returned ${response.statusCode}: ${response.body}');
    }
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    if (data['status'] != 'success') {
      throw Exception(data['message'] ?? 'OCR failed');
    }

    // Current Flask endpoint does not return model confidence yet. Keep this null
    // rather than inventing a confidence value; generic API will supply it later.
    return OcrResult(
      reading: (data['final_output'] ?? '').toString(),
      confidence: data['confidence'] is num ? (data['confidence'] as num).toDouble() : null,
      elapsed: sw.elapsed,
      warnings: data['confidence'] == null ? const ['Current OCR backend does not report confidence.'] : const [],
    );
  }
}
