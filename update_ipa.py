import os, shutil, zipfile, plistlib

def pack_ipa():
    source_ipa = 'ApexProps_orig.ipa' if os.path.exists('ApexProps_orig.ipa') else 'ApexProps.ipa'
    if not os.path.exists('ApexProps_orig.ipa') and os.path.exists('ApexProps.ipa'):
        shutil.copy('ApexProps.ipa', 'ApexProps_orig.ipa')

    temp_dir = 'temp_ipa_extract'
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)

    print('Extracting base IPA from', source_ipa)
    with zipfile.ZipFile(source_ipa, 'r') as zin:
        zin.extractall(temp_dir)

    # Patch Info.plist with app display name
    info_plist_path = os.path.join(temp_dir, 'Payload', 'App.app', 'Info.plist')
    if os.path.exists(info_plist_path):
        try:
            with open(info_plist_path, 'rb') as fp:
                pl = plistlib.load(fp)
            pl['CFBundleDisplayName'] = 'Kalshi_AiTrader'
            pl['CFBundleName'] = 'Kalshi_AiTrader'
            with open(info_plist_path, 'wb') as fp:
                plistlib.dump(pl, fp)
            print('Successfully updated Info.plist CFBundleDisplayName to Kalshi_AiTrader')
        except Exception as e:
            print('Warning updating Info.plist:', e)

    public_dir = os.path.join(temp_dir, 'Payload', 'App.app', 'public')
    os.makedirs(public_dir, exist_ok=True)

    static_dir = 'static'
    for root, dirs, files in os.walk(static_dir):
        rel = os.path.relpath(root, static_dir)
        target_root = os.path.join(public_dir, rel) if rel != '.' else public_dir
        os.makedirs(target_root, exist_ok=True)
        for f in files:
            src_file = os.path.join(root, f)
            dest_file = os.path.join(target_root, f)
            shutil.copy2(src_file, dest_file)

    targets = [
        'Kalshi_AiTrader.ipa',
        'ApexProps.ipa',
        os.path.join('dist', 'Kalshi_AiTrader.ipa'),
        os.path.join('dist', 'ApexProps-iOS-IPA', 'ApexProps.ipa'),
        os.path.join('dist', 'build_latest', 'ApexProps-iOS-IPA', 'ApexProps.ipa')
    ]

    for target_path in targets:
        dir_name = os.path.dirname(target_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        print('Creating', target_path)
        with zipfile.ZipFile(target_path, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
            for root, dirs, files in os.walk(temp_dir):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, temp_dir)
                    zout.write(full, rel)
        size_mb = os.path.getsize(target_path) / (1024 * 1024)
        print(f'Successfully wrote {target_path} ({size_mb:.2f} MB)')

    shutil.rmtree(temp_dir)
    print('IPA repackage complete!')

if __name__ == '__main__':
    pack_ipa()
