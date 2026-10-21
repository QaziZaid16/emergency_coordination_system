import 'dart:convert';

enum Priority { critical, high, medium, low }

enum IncidentStatus { queued, assigned, enRoute, responding, resolved }

enum ResponderStatus { available, assigned, enRoute, responding, offDuty }

String priorityName(Priority value) => switch (value) {
  Priority.critical => 'Critical',
  Priority.high => 'High',
  Priority.medium => 'Medium',
  Priority.low => 'Low',
};
String incidentStatusName(IncidentStatus value) => switch (value) {
  IncidentStatus.queued => 'Queued',
  IncidentStatus.assigned => 'Assigned',
  IncidentStatus.enRoute => 'En route',
  IncidentStatus.responding => 'Responding',
  IncidentStatus.resolved => 'Resolved',
};
String responderStatusName(ResponderStatus value) => switch (value) {
  ResponderStatus.available => 'Available',
  ResponderStatus.assigned => 'Assigned',
  ResponderStatus.enRoute => 'En route',
  ResponderStatus.responding => 'Responding',
  ResponderStatus.offDuty => 'Off duty',
};

class Incident {
  Incident({
    required this.id,
    required this.type,
    required this.description,
    required this.location,
    required this.latitude,
    required this.longitude,
    required this.severity,
    required this.urgency,
    required this.priority,
    required this.priorityReason,
    required this.createdAt,
    this.status = IncidentStatus.queued,
    this.responderId,
    this.resourceId,
    this.resolvedAt,
  });
  final String id, type, description, location, priorityReason;
  final double latitude, longitude;
  final int severity, urgency;
  final Priority priority;
  final DateTime createdAt;
  IncidentStatus status;
  String? responderId, resourceId;
  DateTime? resolvedAt;
  bool get active => status != IncidentStatus.resolved;
  Map<String, dynamic> toJson() => {
    'id': id,
    'type': type,
    'description': description,
    'location': location,
    'latitude': latitude,
    'longitude': longitude,
    'severity': severity,
    'urgency': urgency,
    'priority': priority.name,
    'priorityReason': priorityReason,
    'createdAt': createdAt.toIso8601String(),
    'status': status.name,
    'responderId': responderId,
    'resourceId': resourceId,
    'resolvedAt': resolvedAt?.toIso8601String(),
  };
  factory Incident.fromJson(Map<String, dynamic> j) => Incident(
    id: j['id'],
    type: j['type'],
    description: j['description'],
    location: j['location'],
    latitude: (j['latitude'] as num).toDouble(),
    longitude: (j['longitude'] as num).toDouble(),
    severity: j['severity'],
    urgency: j['urgency'],
    priority: Priority.values.byName(j['priority']),
    priorityReason: j['priorityReason'],
    createdAt: DateTime.parse(j['createdAt']),
    status: IncidentStatus.values.byName(j['status']),
    responderId: j['responderId'],
    resourceId: j['resourceId'],
    resolvedAt: j['resolvedAt'] == null
        ? null
        : DateTime.parse(j['resolvedAt']),
  );
}

class Responder {
  Responder({
    required this.id,
    required this.name,
    required this.team,
    required this.skills,
    required this.latitude,
    required this.longitude,
    this.status = ResponderStatus.available,
    this.incidentId,
  });
  final String id, name, team;
  final List<String> skills;
  final double latitude, longitude;
  ResponderStatus status;
  String? incidentId;
  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'team': team,
    'skills': skills,
    'latitude': latitude,
    'longitude': longitude,
    'status': status.name,
    'incidentId': incidentId,
  };
  factory Responder.fromJson(Map<String, dynamic> j) => Responder(
    id: j['id'],
    name: j['name'],
    team: j['team'],
    skills: List<String>.from(j['skills']),
    latitude: (j['latitude'] as num).toDouble(),
    longitude: (j['longitude'] as num).toDouble(),
    status: ResponderStatus.values.byName(j['status']),
    incidentId: j['incidentId'],
  );
}

class Resource {
  Resource({
    required this.id,
    required this.name,
    required this.type,
    required this.quantity,
    this.incidentId,
  });
  final String id, name, type;
  final int quantity;
  String? incidentId;
  bool get available => incidentId == null;
  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'type': type,
    'quantity': quantity,
    'incidentId': incidentId,
  };
  factory Resource.fromJson(Map<String, dynamic> j) => Resource(
    id: j['id'],
    name: j['name'],
    type: j['type'],
    quantity: j['quantity'],
    incidentId: j['incidentId'],
  );
}

class ChatMessage {
  ChatMessage({
    required this.id,
    required this.incidentId,
    required this.sender,
    required this.role,
    required this.body,
    required this.sentAt,
  });
  final String id, incidentId, sender, role, body;
  final DateTime sentAt;
  Map<String, dynamic> toJson() => {
    'id': id,
    'incidentId': incidentId,
    'sender': sender,
    'role': role,
    'body': body,
    'sentAt': sentAt.toIso8601String(),
  };
  factory ChatMessage.fromJson(Map<String, dynamic> j) => ChatMessage(
    id: j['id'],
    incidentId: j['incidentId'],
    sender: j['sender'],
    role: j['role'],
    body: j['body'],
    sentAt: DateTime.parse(j['sentAt']),
  );
}

class ActivityEvent {
  ActivityEvent({
    required this.id,
    required this.incidentId,
    required this.title,
    required this.detail,
    required this.at,
  });
  final String id, incidentId, title, detail;
  final DateTime at;
  Map<String, dynamic> toJson() => {
    'id': id,
    'incidentId': incidentId,
    'title': title,
    'detail': detail,
    'at': at.toIso8601String(),
  };
  factory ActivityEvent.fromJson(Map<String, dynamic> j) => ActivityEvent(
    id: j['id'],
    incidentId: j['incidentId'],
    title: j['title'],
    detail: j['detail'],
    at: DateTime.parse(j['at']),
  );
}

String encodeList<T>(List<T> list, Map<String, dynamic> Function(T) map) =>
    jsonEncode(list.map(map).toList());
