// Keep the existing QtQuickTest fake-host module pointed at the real D2 screens.
const fs = require('fs');
const path = require('path');
const dir = path.join(__dirname, '../tests/qml/stub/ABook/qmldir');
let source = fs.readFileSync(dir, 'utf8').replace(/\r/g, '');
const names = ['FormLabel', 'FormField', 'SettingRow', 'SettingChoices', 'SectionBlock', 'Modal', 'SettingsBody', 'SettingsVoice', 'VoiceModule', 'ProviderKey', 'SettingsDevices', 'SettingsStudio', 'MyMusicSettings', 'NativeFolders', 'ThirdPartyText', 'AddBook', 'EditBook', 'CoverSearch', 'BookMusicSettings'];
for (const name of names) if (!source.includes('\n' + name + ' 1.0 ')) source += `${name} 1.0 ../../../../qml/${name}.qml\n`;
if (!source.includes('\nsingleton Api ')) source += 'singleton Api 1.0 ../../../../qml/Api.qml\n';
if (!source.includes('\nsingleton DesktopApi ')) source += 'singleton DesktopApi 1.0 DesktopApi.qml\n';
fs.writeFileSync(dir, source);
