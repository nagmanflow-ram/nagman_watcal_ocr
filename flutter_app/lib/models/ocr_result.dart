class OcrResult {
  final String reading;
  final double confidence;
  final Duration elapsed;
  final List<String> warnings;

  const OcrResult({
    required this.reading,
    required this.confidence,
    required this.elapsed,
    this.warnings = const [],
  });
}
