
import os

path = r"C:\Users\Vill3\Desktop\ShadowTraderAi\.github\workflows\build-ios.yml"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old_build_step = """      - name: Build iOS App (Unsigned for Sideloading)
        run: |
          cd ios/App
          # We build an unsigned payload because Sideloadly/AltStore signs it on the users machine
          xcodebuild -workspace App.xcworkspace -scheme App -configuration Release -sdk iphoneos CODE_SIGN_IDENTITY="" CODE_SIGNING_REQUIRED=NO CODE_SIGNING_ALLOWED=NO build
          
          # Package the .app into a Payload folder to create an .ipa
          mkdir -p Payload
          mv build/Release-iphoneos/App.app Payload/
          zip -r ../../ShadowTrade.ipa Payload"""

new_build_step = """      - name: Build iOS App (Unsigned for Sideloading)
        run: |
          cd ios/App
          
          echo "Starting Xcode Build..."
          set -o pipefail
          xcodebuild clean build -workspace App.xcworkspace -scheme App -configuration Release -sdk iphoneos CONFIGURATION_BUILD_DIR="$(pwd)/build/Release-iphoneos" CODE_SIGN_IDENTITY="" CODE_SIGNING_REQUIRED=NO CODE_SIGNING_ALLOWED=NO | tee build_raw.log | xcpretty || {
            echo "========================================="
            echo "? XCODE BUILD FAILED! SCANNING FOR ERRORS:"
            echo "========================================="
            grep -A 5 -B 2 -i "error:" build_raw.log
            exit 65
          }
          
          echo "Build successful! Packaging IPA..."
          mkdir -p Payload
          mv build/Release-iphoneos/App.app Payload/
          zip -r ../../ShadowTrade.ipa Payload"""

content = content.replace(old_build_step, new_build_step)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

