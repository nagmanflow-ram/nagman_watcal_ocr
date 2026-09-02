import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../models/meter_profile.dart';

class ProfileWizard extends StatefulWidget {
  const ProfileWizard({super.key});

  @override
  State<ProfileWizard> createState() => _ProfileWizardState();
}

class _ProfileWizardState extends State<ProfileWizard> {
  final _name = TextEditingController(text: 'New Water Meter');
  final _uuid = const Uuid();
  String _unit = 'm³';
  LayoutMode _layout = LayoutMode.freeform;
  int _rotation = 0;
  int _counterDigits = 6;
  int _counterDecimals = 1;
  double _counterMultiplier = 1;
  final List<MeterDial> _dials = [];
  int _step = 0;

  void _addDial() {
    final n = _dials.length + 1;
    setState(() {
      _dials.add(MeterDial(
        id: _uuid.v4(),
        name: 'Dial $n',
        x: 0.18 + ((_dials.length % 3) * 0.30),
        y: 0.70 - ((_dials.length ~/ 3) * 0.24),
        multiplier: 1 / (10 * n),
        unit: _unit,
        direction: n.isOdd ? DialDirection.clockwise : DialDirection.counterClockwise,
        zeroAngle: 270,
      ));
    });
  }

  void _editDial(int index) async {
    var dial = _dials[index];
    final multiplier = TextEditingController(text: dial.multiplier.toString());
    final name = TextEditingController(text: dial.name);
    DialDirection direction = dial.direction;
    final saved = await showDialog<MeterDial>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setLocal) => AlertDialog(
          title: const Text('Dial settings'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(controller: name, decoration: const InputDecoration(labelText: 'Dial name')),
            TextField(controller: multiplier, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: const InputDecoration(labelText: 'Multiplication factor')),
            const SizedBox(height: 12),
            SegmentedButton<DialDirection>(
              segments: const [
                ButtonSegment(value: DialDirection.clockwise, label: Text('Clockwise'), icon: Icon(Icons.rotate_right)),
                ButtonSegment(value: DialDirection.counterClockwise, label: Text('Anti-clockwise'), icon: Icon(Icons.rotate_left)),
              ],
              selected: {direction},
              onSelectionChanged: (v) => setLocal(() => direction = v.first),
            ),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
            FilledButton(
              onPressed: () => Navigator.pop(context, dial.copyWith(
                name: name.text.trim().isEmpty ? dial.name : name.text.trim(),
                multiplier: double.tryParse(multiplier.text) ?? dial.multiplier,
                direction: direction,
                unit: _unit,
              )),
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
    if (saved != null) setState(() => _dials[index] = saved);
  }

  Widget _meterCanvas() {
    return AspectRatio(
      aspectRatio: 1.35,
      child: LayoutBuilder(
        builder: (context, c) => Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: Colors.blueGrey.shade100, width: 2),
          ),
          child: Stack(children: [
            Positioned(
              left: c.maxWidth * .17,
              top: c.maxHeight * .12,
              width: c.maxWidth * .66,
              child: Container(
                height: 58,
                decoration: BoxDecoration(color: Colors.grey.shade900, borderRadius: BorderRadius.circular(10)),
                alignment: Alignment.center,
                child: Text(
                  List.generate(_counterDigits, (i) => i >= _counterDigits - _counterDecimals ? '8' : '0').join(),
                  style: const TextStyle(color: Colors.white, fontSize: 28, letterSpacing: 6, fontWeight: FontWeight.w700),
                ),
              ),
            ),
            ...List.generate(_dials.length, (i) {
              final d = _dials[i];
              final size = 72.0;
              return Positioned(
                left: (d.x * c.maxWidth - size / 2).clamp(0, c.maxWidth - size),
                top: (d.y * c.maxHeight - size / 2).clamp(0, c.maxHeight - size),
                child: GestureDetector(
                  onPanUpdate: (details) {
                    setState(() {
                      final nx = (d.x + details.delta.dx / c.maxWidth).clamp(0.08, 0.92);
                      final ny = (d.y + details.delta.dy / c.maxHeight).clamp(0.20, 0.92);
                      _dials[i] = d.copyWith(x: nx, y: ny);
                    });
                  },
                  onTap: () => _editDial(i),
                  child: Container(
                    width: size,
                    height: size,
                    decoration: BoxDecoration(shape: BoxShape.circle, color: Colors.white, border: Border.all(color: Theme.of(context).colorScheme.primary, width: 3), boxShadow: const [BoxShadow(blurRadius: 8, color: Color(0x22000000))]),
                    child: Stack(alignment: Alignment.center, children: [
                      const Icon(Icons.speed, size: 40),
                      Positioned(bottom: 2, child: Container(padding: const EdgeInsets.symmetric(horizontal: 4), color: Colors.white, child: Text('×${d.multiplier}', style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold)))),
                      Positioned(top: 2, right: 3, child: Icon(d.direction == DialDirection.clockwise ? Icons.rotate_right : Icons.rotate_left, size: 15)),
                    ]),
                  ),
                ),
              );
            }),
            if (_dials.isEmpty)
              const Positioned.fill(child: Center(child: Text('Add dials below, then drag them\nto match the physical meter.', textAlign: TextAlign.center))),
          ]),
        ),
      ),
    );
  }

  void _save() {
    Navigator.pop(context, MeterProfile(
      id: _uuid.v4(),
      name: _name.text.trim().isEmpty ? 'Water Meter' : _name.text.trim(),
      baseUnit: _unit,
      layout: _layout,
      imageRotation: _rotation,
      counterDigits: _counterDigits,
      counterDecimals: _counterDecimals,
      counterMultiplier: _counterMultiplier,
      dials: List.unmodifiable(_dials),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      ListView(padding: const EdgeInsets.all(20), children: [
        TextField(controller: _name, decoration: const InputDecoration(labelText: 'Meter profile name', border: OutlineInputBorder())),
        const SizedBox(height: 18),
        DropdownButtonFormField<String>(value: _unit, decoration: const InputDecoration(labelText: 'Engineering unit', border: OutlineInputBorder()), items: const ['m³', 'L', 'kL', 'gal'].map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(), onChanged: (v) => setState(() => _unit = v!)),
        const SizedBox(height: 18),
        DropdownButtonFormField<LayoutMode>(value: _layout, decoration: const InputDecoration(labelText: 'Dial layout', border: OutlineInputBorder()), items: LayoutMode.values.map((e) => DropdownMenuItem(value: e, child: Text(e.name))).toList(), onChanged: (v) => setState(() => _layout = v!)),
        const SizedBox(height: 18),
        DropdownButtonFormField<int>(value: _rotation, decoration: const InputDecoration(labelText: 'Meter image orientation', border: OutlineInputBorder()), items: const [0, 90, 180, 270].map((e) => DropdownMenuItem(value: e, child: Text('$e°'))).toList(), onChanged: (v) => setState(() => _rotation = v!)),
      ]),
      ListView(padding: const EdgeInsets.all(20), children: [
        const Text('Counter / odometer', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        Text('Digits: $_counterDigits'),
        Slider(value: _counterDigits.toDouble(), min: 0, max: 10, divisions: 10, onChanged: (v) => setState(() { _counterDigits = v.round(); _counterDecimals = _counterDecimals.clamp(0, _counterDigits); })),
        Text('Decimal digits: $_counterDecimals'),
        Slider(value: _counterDecimals.toDouble(), min: 0, max: _counterDigits == 0 ? 1 : _counterDigits.toDouble(), divisions: _counterDigits == 0 ? 1 : _counterDigits, onChanged: (v) => setState(() => _counterDecimals = _counterDigits == 0 ? 0 : v.round())),
        TextFormField(initialValue: '1', decoration: const InputDecoration(labelText: 'Counter multiplication factor', border: OutlineInputBorder()), keyboardType: const TextInputType.numberWithOptions(decimal: true), onChanged: (v) => _counterMultiplier = double.tryParse(v) ?? 1),
        const SizedBox(height: 24),
        _meterCanvas(),
      ]),
      ListView(padding: const EdgeInsets.all(20), children: [
        Row(children: [Expanded(child: Text('${_dials.length} rotary dial${_dials.length == 1 ? '' : 's'}', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold))), FilledButton.icon(onPressed: _addDial, icon: const Icon(Icons.add), label: const Text('Add dial'))]),
        const SizedBox(height: 14),
        _meterCanvas(),
        const SizedBox(height: 14),
        ...List.generate(_dials.length, (i) => Card(child: ListTile(onTap: () => _editDial(i), leading: const CircleAvatar(child: Icon(Icons.speed)), title: Text(_dials[i].name), subtitle: Text('${_dials[i].direction == DialDirection.clockwise ? 'Clockwise' : 'Anti-clockwise'} • ×${_dials[i].multiplier} ${_dials[i].unit}'), trailing: IconButton(icon: const Icon(Icons.delete_outline), onPressed: () => setState(() => _dials.removeAt(i))))),
        const SizedBox(height: 18),
        FilledButton.icon(onPressed: _save, icon: const Icon(Icons.check_circle), label: const Padding(padding: EdgeInsets.all(12), child: Text('Save Meter Profile'))),
      ]),
    ];

    return Scaffold(
      appBar: AppBar(title: const Text('Configure Meter')),
      body: Column(children: [
        Padding(padding: const EdgeInsets.symmetric(horizontal: 20), child: LinearProgressIndicator(value: (_step + 1) / 3, minHeight: 7, borderRadius: BorderRadius.circular(10))),
        const SizedBox(height: 8),
        Text(['Basics', 'Counter & Preview', 'Dial Layout'][_step], style: const TextStyle(fontWeight: FontWeight.w700)),
        Expanded(child: pages[_step]),
        if (_step < 2)
          SafeArea(child: Padding(padding: const EdgeInsets.fromLTRB(20, 8, 20, 12), child: Row(children: [if (_step > 0) Expanded(child: OutlinedButton(onPressed: () => setState(() => _step--), child: const Text('Back'))), if (_step > 0) const SizedBox(width: 12), Expanded(child: FilledButton(onPressed: () => setState(() => _step++), child: const Text('Next')))]))),
      ]),
    );
  }
}
