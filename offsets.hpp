// Offsets refreshed 2026-09-25 07:07 UTC from a2x/cs2-dumper main output
// (https://github.com/a2x/cs2-dumper, output/offsets.hpp + output/client_dll.hpp).
// The dw* globals moved with today's CS2 update; the m_* schema fields were
// re-verified against the same dump and are unchanged.
// CS2 updates invalidate these. To refresh after a game update, either pull
// the two output files above or rebuild and re-run the dumper against the
// live cs2.exe process:
//   cargo build --release
//   .\target\release\cs2-dumper.exe -o output-local -f hpp,json
//   output-local\offsets.hpp      -> the dw* globals in namespace offsets
//   output-local\client_dll.hpp   -> the schema fields in namespace schemas

#pragma once

#include <cstddef>
#include <cstdint>

namespace cs2_dumper {
    namespace offsets {
        // Module: client.dll
        namespace client_dll {
            constexpr std::ptrdiff_t dwEntityList             = 0x27130E8;
            constexpr std::ptrdiff_t dwGlobalVars             = 0x2229F88;
            constexpr std::ptrdiff_t dwLocalPlayerController  = 0x2535598;
            constexpr std::ptrdiff_t dwLocalPlayerPawn        = 0x255E658;
            constexpr std::ptrdiff_t dwViewMatrix             = 0x25639A0;
        }
    }

    namespace schemas {
        // Module: client.dll
        namespace client_dll {
            // C_BaseEntity
            namespace C_BaseEntity {
                constexpr std::ptrdiff_t m_pGameSceneNode = 0x330;  // CGameSceneNode*
                constexpr std::ptrdiff_t m_iHealth        = 0x34C;  // int32
                constexpr std::ptrdiff_t m_lifeState      = 0x354;  // uint8 (0 = alive)
                constexpr std::ptrdiff_t m_iTeamNum       = 0x3E7;  // uint8 (2 = T, 3 = CT)
            }

            // CGameSceneNode
            namespace CGameSceneNode {
                constexpr std::ptrdiff_t m_vecAbsOrigin   = 0xC8;   // VectorWS
                constexpr std::ptrdiff_t m_bDormant       = 0x103;  // bool
            }

            // C_BaseModelEntity (inherited by player pawns)
            namespace C_BaseModelEntity {
                constexpr std::ptrdiff_t m_vecViewOffset  = 0xF60;  // eye offset above origin
            }

            // CBasePlayerController (inherited by CCSPlayerController)
            namespace CBasePlayerController {
                constexpr std::ptrdiff_t m_iszPlayerName            = 0x6FC;  // char[128]
                constexpr std::ptrdiff_t m_bIsLocalPlayerController = 0x790;  // bool
            }

            // CCSPlayerController
            namespace CCSPlayerController {
                constexpr std::ptrdiff_t m_hPlayerPawn  = 0x92C;  // CHandle<C_CSPlayerPawn>
                constexpr std::ptrdiff_t m_hObserverPawn = 0x930; // CHandle — pawn attached while observing
                constexpr std::ptrdiff_t m_bPawnIsAlive = 0x934;  // bool
                constexpr std::ptrdiff_t m_iPawnHealth  = 0x938;  // uint32
            }

            // C_CSPlayerPawn
            namespace C_CSPlayerPawn {
                constexpr std::ptrdiff_t m_entitySpottedState = 0x1E88; // EntitySpottedState_t
                constexpr std::ptrdiff_t m_iIDEntIndex         = 0x36CC; // CEntityIndex under crosshair
                constexpr std::ptrdiff_t m_bIsScoped           = 0x1EA0; // bool (local player)
                constexpr std::ptrdiff_t m_iShotsFired         = 0x1EB4; // int32 (jump = a shot fired)
                constexpr std::ptrdiff_t m_angEyeAngles        = 0x35F0; // QAngle (pitch, yaw, roll)
            }

            // EntitySpottedState_t (embedded in player pawns)
            namespace EntitySpottedState_t {
                constexpr std::ptrdiff_t m_bSpotted       = 0x8;  // bool (spotted by anyone)
                constexpr std::ptrdiff_t m_bSpottedByMask = 0xC;  // uint32[2] — observers with current line of sight
            }

            // active-weapon chain (knife detection) + observer chain (spectators)
            namespace C_BasePlayerPawn {
                constexpr std::ptrdiff_t m_pWeaponServices  = 0x12F0; // CPlayer_WeaponServices*
                constexpr std::ptrdiff_t m_pObserverServices = 0x1308; // CPlayer_ObserverServices* (null unless observing)
            }
            namespace CPlayer_ObserverServices {
                constexpr std::ptrdiff_t m_iObserverMode   = 0x48; // uint8 (0 = none, 4 = in-eye, 5 = chase, 6 = roaming)
                constexpr std::ptrdiff_t m_hObserverTarget = 0x4C; // CHandle<C_BaseEntity> — who they are watching
            }
            namespace CPlayer_WeaponServices {
                constexpr std::ptrdiff_t m_hActiveWeapon = 0x60; // CHandle<C_BasePlayerWeapon>
            }
            namespace C_EconEntity {
                constexpr std::ptrdiff_t m_AttributeManager = 0x1290; // C_AttributeContainer (embedded)
            }
            namespace C_AttributeContainer {
                constexpr std::ptrdiff_t m_Item = 0x50; // C_EconItemView (embedded)
            }
            namespace C_EconItemView {
                constexpr std::ptrdiff_t m_iItemDefinitionIndex = 0x1BA; // uint16
            }
        }
    }
}
