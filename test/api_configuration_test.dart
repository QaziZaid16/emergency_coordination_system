import 'package:emergency_coordination_system/data/api_configuration.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('release requires a real HTTPS API origin', () {
    expect(
      ApiConfiguration(
        'https://api.coordination-platform.net',
        releaseMode: true,
      ).isValid,
      isTrue,
    );
    expect(
      ApiConfiguration('https://your-api-host', releaseMode: true).isValid,
      isFalse,
    );
    expect(
      ApiConfiguration('http://api.example.net', releaseMode: true).isValid,
      isFalse,
    );
    expect(
      ApiConfiguration('https://api.example.test', releaseMode: true).isValid,
      isFalse,
    );
    expect(
      ApiConfiguration('https://api.example.com', releaseMode: true).isValid,
      isFalse,
    );
  });

  test('debug HTTP allows loopback and private LAN addresses only', () {
    expect(
      ApiConfiguration('http://127.0.0.1:8000', releaseMode: false).isValid,
      isTrue,
    );
    expect(
      ApiConfiguration('http://10.0.2.2:8000', releaseMode: false).isValid,
      isTrue,
    );
    for (final address in [
      'http://10.12.0.4:8000',
      'http://172.16.0.4:8000',
      'http://172.31.255.254:8000',
      'http://192.168.1.42:8000',
      'http://[fd12:3456::10]:8000',
      'http://[fc00::1]:8000',
    ]) {
      expect(
        ApiConfiguration(address, releaseMode: false).isValid,
        isTrue,
        reason: address,
      );
    }
    expect(
      ApiConfiguration(
        'http://coordination.example.net',
        releaseMode: false,
      ).isValid,
      isFalse,
    );
    for (final address in [
      'http://8.8.8.8:8000',
      'http://172.32.0.1:8000',
      'http://192.167.1.1:8000',
      'http://[2001:4860:4860::8888]:8000',
      'http://[fe80::1]:8000',
    ]) {
      expect(
        ApiConfiguration(address, releaseMode: false).isValid,
        isFalse,
        reason: address,
      );
    }
    expect(ApiConfiguration('', releaseMode: false).isValid, isFalse);
    expect(ApiConfiguration('not a url', releaseMode: false).isValid, isFalse);
    expect(
      ApiConfiguration('http://user@192.168.1.2:8000', releaseMode: false)
          .isValid,
      isFalse,
    );
    expect(
      ApiConfiguration('http://192.168.1.2:8000?token=x', releaseMode: false)
          .isValid,
      isFalse,
    );
  });

  test('release mode never permits cleartext LAN URLs', () {
    for (final address in [
      'http://127.0.0.1:8000',
      'http://192.168.1.42:8000',
      'http://[fd12:3456::10]:8000',
    ]) {
      expect(
        ApiConfiguration(address, releaseMode: true).isValid,
        isFalse,
        reason: address,
      );
    }
    expect(
      ApiConfiguration('https://192.168.1.42:8000', releaseMode: true).isValid,
      isTrue,
    );
  });
}
