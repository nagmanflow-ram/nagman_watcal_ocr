import 'dart:convert';

enum DialDirection { clockwise, counterClockwise }
enum LayoutMode { horizontal, vertical, grid, radial, freeform }

class MeterDial {
  final String id;
  final String name;
  final double x;
  final double y;
  final double multiplier;
  final String unit;
  final DialDirection direction;
  final double zeroAngle;

  const MeterDial({
    required this.id,
    required this.name,
    required this.x,
    required this.y,
    required this.multiplier,
    required this.unit,
    required this.direction,
    required this.zeroAngle,
  });

  MeterDial copyWith({
    String? id,
    String? name,
    double? x,
    double? y,
    double? multiplier,
    String? unit,
    DialDirection? direction,
    double? zeroAngle,
  }) => MeterDial(
        id: id ?? this.id,
        name: name ?? this.name,
        x: x ?? this.x,
        y: y ?? this.y,
        multiplier: multiplier ?? this.multiplier,
        unit: unit ?? this.unit,
        direction: direction ?? this.direction,
        zeroAngle: zeroAngle ?? this.zeroAngle,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'x': x,
        'y': y,
        'multiplier': multiplier,
        'unit': unit,
        'direction': direction.name,
        'zeroAngle': zeroAngle,
      };

  factory MeterDial.fromJson(Map<String, dynamic> json) => MeterDial(
        id: json['id'],
        name: json['name'],
        x: (json['x'] as num).toDouble(),
        y: (json['y'] as num).toDouble(),
        multiplier: (json['multiplier'] as num).toDouble(),
        unit: json['unit'],
        direction: DialDirection.values.byName(json['direction']),
        zeroAngle: (json['zeroAngle'] as num).toDouble(),
      );
}

class MeterProfile {
  final String id;
  final String name;
  final String baseUnit;
  final LayoutMode layout;
  final int imageRotation;
  final int counterDigits;
  final int counterDecimals;
  final double counterMultiplier;
  final List<MeterDial> dials;

  const MeterProfile({
    required this.id,
    required this.name,
    required this.baseUnit,
    required this.layout,
    required this.imageRotation,
    required this.counterDigits,
    required this.counterDecimals,
    required this.counterMultiplier,
    required this.dials,
  });

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'baseUnit': baseUnit,
        'layout': layout.name,
        'imageRotation': imageRotation,
        'counterDigits': counterDigits,
        'counterDecimals': counterDecimals,
        'counterMultiplier': counterMultiplier,
        'dials': dials.map((e) => e.toJson()).toList(),
      };

  String encode() => jsonEncode(toJson());

  factory MeterProfile.fromJson(Map<String, dynamic> json) => MeterProfile(
        id: json['id'],
        name: json['name'],
        baseUnit: json['baseUnit'],
        layout: LayoutMode.values.byName(json['layout']),
        imageRotation: json['imageRotation'] ?? 0,
        counterDigits: json['counterDigits'] ?? 0,
        counterDecimals: json['counterDecimals'] ?? 0,
        counterMultiplier: (json['counterMultiplier'] ?? 1).toDouble(),
        dials: (json['dials'] as List<dynamic>? ?? [])
            .map((e) => MeterDial.fromJson(Map<String, dynamic>.from(e)))
            .toList(),
      );

  factory MeterProfile.decode(String value) =>
      MeterProfile.fromJson(jsonDecode(value));
}
