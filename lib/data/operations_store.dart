import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';

import '../domain/dispatch_rules.dart';
import '../domain/models.dart';

class OperationsStore extends ChangeNotifier {
  OperationsStore(this.file);
  final File file;
  final List<Incident> incidents = [];
  final List<Responder> responders = [];
  final List<Resource> resources = [];
  final List<ChatMessage> messages = [];
  final List<ActivityEvent> events = [];
  String? storageError;
  bool _seeded = false;

  Future<void> load() async {
    try {
      if (await file.exists()) {
        final document = Map<String, dynamic>.from(
          jsonDecode(await file.readAsString()) as Map,
        );
        _seeded = document['seeded'] == true;
        _read(
          document,
          'incidents',
          (j) => incidents.add(Incident.fromJson(j)),
        );
        _read(
          document,
          'responders',
          (j) => responders.add(Responder.fromJson(j)),
        );
        _read(
          document,
          'resources',
          (j) => resources.add(Resource.fromJson(j)),
        );
        _read(
          document,
          'messages',
          (j) => messages.add(ChatMessage.fromJson(j)),
        );
        _read(document, 'events', (j) => events.add(ActivityEvent.fromJson(j)));
      }
      if (!_seeded) await seed();
    } catch (e) {
      storageError = 'Saved workspace could not be read: $e';
    }
  }

  void _read(
    Map<String, dynamic> document,
    String key,
    void Function(Map<String, dynamic>) add,
  ) {
    final rows = document[key] as List? ?? const [];
    for (final row in rows) {
      add(Map<String, dynamic>.from(row as Map));
    }
  }

  Future<void> seed() async {
    final now = DateTime.now();
    responders.addAll([
      Responder(
        id: 'r1',
        name: 'Aarav Mehta',
        team: 'Medical unit',
        skills: ['Medical', 'Rescue'],
        latitude: 30.7045,
        longitude: 76.7179,
      ),
      Responder(
        id: 'r2',
        name: 'Simran Kaur',
        team: 'Fire response',
        skills: ['Fire', 'Rescue'],
        latitude: 30.7102,
        longitude: 76.7215,
      ),
      Responder(
        id: 'r3',
        name: 'Kabir Singh',
        team: 'Field support',
        skills: ['Security', 'Utility'],
        latitude: 30.6958,
        longitude: 76.7301,
      ),
      Responder(
        id: 'r4',
        name: 'Noor Sharma',
        team: 'Medical unit',
        skills: ['Medical'],
        latitude: 30.7220,
        longitude: 76.7061,
      ),
    ]);
    resources.addAll([
      Resource(id: 'v1', name: 'Ambulance 04', type: 'Medical', quantity: 1),
      Resource(id: 'v2', name: 'Fire engine 02', type: 'Fire', quantity: 1),
      Resource(id: 'v3', name: 'Rescue van 01', type: 'Rescue', quantity: 1),
      Resource(
        id: 'v4',
        name: 'Utility vehicle 03',
        type: 'Utility',
        quantity: 1,
      ),
    ]);
    final d = assessPriority(type: 'Medical', severity: 5, urgency: 5);
    final sample = Incident(
      id: 'i-demo-1',
      type: 'Medical',
      description: 'Sample record — review patient condition and coordinate nearby support.',
      location: 'Sector 68, Mohali',
      latitude: 30.7047,
      longitude: 76.7185,
      severity: 5,
      urgency: 5,
      priority: d.priority,
      priorityReason: d.reason,
      createdAt: now.subtract(const Duration(minutes: 12)),
    );
    incidents.add(sample);
    _event(
      sample.id,
      'Sample incident loaded',
      'Simulated training record. No real emergency has been reported.',
    );
    await _save();
  }

  String _id(String prefix) =>
      '$prefix-${DateTime.now().microsecondsSinceEpoch}';
  Future<void> _save() async {
    try {
      await file.parent.create(recursive: true);
      await file.writeAsString(
        jsonEncode({
          'seeded': true,
          'incidents': incidents.map((x) => x.toJson()).toList(),
          'responders': responders.map((x) => x.toJson()).toList(),
          'resources': resources.map((x) => x.toJson()).toList(),
          'messages': messages.map((x) => x.toJson()).toList(),
          'events': events.map((x) => x.toJson()).toList(),
        }),
        flush: true,
      );
      _seeded = true;
      storageError = null;
    } catch (e) {
      storageError = 'Changes could not be saved on this device: $e';
    }
    notifyListeners();
  }

  void _event(String iid, String title, String detail) => events.insert(
    0,
    ActivityEvent(
      id: _id('evt'),
      incidentId: iid,
      title: title,
      detail: detail,
      at: DateTime.now(),
    ),
  );
  List<Incident> get activeIncidents =>
      incidents.where((i) => i.active).toList()..sort((a, b) {
        final p = a.priority.index.compareTo(b.priority.index);
        return p != 0 ? p : b.createdAt.compareTo(a.createdAt);
      });
  List<Incident> get history =>
      incidents.where((i) => !i.active).toList()
        ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
  List<Responder> recommendations(Incident i) {
    final list = responders
        .where(
          (r) =>
              r.status == ResponderStatus.available &&
              r.incidentId == null &&
              r.skills.contains(i.type),
        )
        .toList();
    list.sort((a, b) {
      final d = distanceKm(
        a.latitude,
        a.longitude,
        i.latitude,
        i.longitude,
      ).compareTo(distanceKm(b.latitude, b.longitude, i.latitude, i.longitude));
      return d != 0 ? d : a.skills.length.compareTo(b.skills.length);
    });
    return list;
  }

  Future<Incident> createIncident({
    required String type,
    required String description,
    required String location,
    required double lat,
    required double lon,
    required int severity,
    required int urgency,
  }) async {
    if (description.trim().isEmpty || location.trim().isEmpty) {
      throw ArgumentError('Description and location are required.');
    }
    final d = assessPriority(type: type, severity: severity, urgency: urgency);
    final i = Incident(
      id: _id('inc'),
      type: type,
      description: description.trim(),
      location: location.trim(),
      latitude: lat,
      longitude: lon,
      severity: severity,
      urgency: urgency,
      priority: d.priority,
      priorityReason: d.reason,
      createdAt: DateTime.now(),
    );
    incidents.add(i);
    _event(
      i.id,
      'Incident registered',
      '${i.type} • ${priorityName(i.priority)} priority • ${i.location}',
    );
    await _save();
    return i;
  }

  Future<void> assign(Incident i, Responder r) async {
    if (!i.active || i.status != IncidentStatus.queued) {
      throw StateError('This incident is not awaiting assignment.');
    }
    if (!recommendations(i).any((x) => x.id == r.id)) {
      throw StateError('Responder is no longer available or suitable.');
    }
    i.responderId = r.id;
    i.status = IncidentStatus.assigned;
    r.incidentId = i.id;
    r.status = ResponderStatus.assigned;
    final available = resources
        .where((x) => x.type == i.type && x.available)
        .toList();
    if (available.isNotEmpty) {
      i.resourceId = available.first.id;
      available.first.incidentId = i.id;
    }
    _event(
      i.id,
      'Responder assigned',
      '${r.name}${i.resourceId == null ? '' : ' • ${resources.firstWhere((x) => x.id == i.resourceId).name}'}',
    );
    await _save();
  }

  Future<void> advance(Incident i) async {
    final next = switch (i.status) {
      IncidentStatus.assigned => IncidentStatus.enRoute,
      IncidentStatus.enRoute => IncidentStatus.responding,
      IncidentStatus.responding => IncidentStatus.resolved,
      _ => throw StateError('No next status is available.'),
    };
    if (!canTransition(i.status, next)) {
      throw StateError('Invalid incident status transition.');
    }
    i.status = next;
    final r = responders.where((x) => x.id == i.responderId).firstOrNull;
    if (r != null) {
      r.status = switch (next) {
        IncidentStatus.enRoute => ResponderStatus.enRoute,
        IncidentStatus.responding => ResponderStatus.responding,
        IncidentStatus.resolved => ResponderStatus.available,
        _ => r.status,
      };
      if (next == IncidentStatus.resolved) r.incidentId = null;
    }
    if (next == IncidentStatus.resolved) {
      i.resolvedAt = DateTime.now();
      for (final x in resources.where((x) => x.incidentId == i.id)) {
        x.incidentId = null;
      }
    }
    _event(i.id, 'Status updated', incidentStatusName(next));
    await _save();
  }

  Future<void> setAvailability(Responder responder, bool available) async {
    if (responder.incidentId != null) {
      throw StateError('An assigned responder cannot be taken off duty.');
    }
    responder.status = available
        ? ResponderStatus.available
        : ResponderStatus.offDuty;
    _event(
      'system',
      'Availability changed',
      '${responder.name} is now ${available ? 'available' : 'off duty'}.',
    );
    await _save();
  }

  Future<void> sendMessage(
    Incident i, {
    required String sender,
    required String role,
    required String body,
  }) async {
    final text = body.trim();
    if (text.isEmpty) throw ArgumentError('Message cannot be empty.');
    messages.insert(
      0,
      ChatMessage(
        id: _id('msg'),
        incidentId: i.id,
        sender: sender,
        role: role,
        body: text,
        sentAt: DateTime.now(),
      ),
    );
    _event(i.id, 'Message added', '$sender: $text');
    await _save();
  }

  List<ChatMessage> thread(String id) =>
      messages.where((m) => m.incidentId == id).toList()
        ..sort((a, b) => a.sentAt.compareTo(b.sentAt));
  List<ActivityEvent> incidentEvents(String id) =>
      events.where((e) => e.incidentId == id).toList();
}
