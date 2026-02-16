using System;
using System.Collections.Generic;

public class SDBMHash
{
	public uint Value { get; private set; }

	public SDBMHash(string cStr)
	{
		Value = Hash(cStr);
	}

	private static uint Hash(string str)
	{
		var ret = 0u;
		foreach (var chr in str)
		{
			if (chr >= 0x80)
			{
				throw new NotImplementedException();
			}

			var lower = char.ToLower(chr);
			ret = lower + 65599 * ret;
		}

		return ret;
	}

	public override string ToString()
	{
		if (PrecomputedHashes.TryGetValue(Value, out var list))
		{
			if (list.Count == 1)
			{
				return $"{Value:X8} ({list[0]})";
			}

			throw new NotImplementedException();
		}

		return $"{Value:X8}";
	}

	public static Dictionary<uint, List<string>> PrecomputedHashes = new();

	public static void PrecomputeHashes()
	{
		PrecomputedHashes.Clear();

		foreach (var item in KnownHashedStrings)
		{
			var hash = Hash(item);
			if (PrecomputedHashes.ContainsKey(hash))
			{
				PrecomputedHashes[hash].Add(item);
			}
			else
			{
				PrecomputedHashes.Add(hash, new List<string>() { item });
			}
		}
	}

	public static List<string> KnownHashedStrings = new()
	{
		"AndEventGate",
		"Animated",
		"AnimatedShaderController",
		"Attacher",
		"BartPlayer",
		"Base",
		"BoomOperator",
		"BoundingVolumeCameraModifierInfo",
		"BusStop",
		"CameraInfo",
		"CameraTrigger",
		"ChatterAssetSet",
		"ChatterAssetSetAdd",
		"ChatterAssetSetRemove",
		"ChatterGlobalCullingDistance",
		"Checkpoint",
		"Collectible",
		"CollectObjectsTuningRelay",
		"CombatKnowledgeTuningRelay",
		"ConversationPool",
		"Counter",
		"CrowdAudio",
		"DamageableProp",
		"DeathSequencer",
		"Destructible",
		"DestructibleDynamicObject",
		"DissolvePlatform",
		"Door",
		"DynamicObjectAudio",
		"DynamicObjectBehavior",
		"DynamicObjectTrigger",
		"EnterExitTrigger",
		"Entity",
		"EntityDamageDealer",
		"EntityDensityManager",
		"EntityFilter",
		"EntityList",
		"EntityMeter",
		"EpisodeComplete",
		"EpisodeLauncher",
		"EquipCommand",
		"EventText",
		"ExecuteVFX",
		"ExplodingItem",
		"FadeScreenFx",
		"FleeArea",
		"Fogger",
		"FollowTargetRelay",
		"Food",
		"FreelookCameraInfo",
		"Fulcrum",
		"FuncConveyorBelt",
		"FuncMover",
		"FuncPusher",
		"FuncRotate",
		"FuncSpawn",
		"FXObject",
		"FXObjectHandle",
		"GraphMoverController",
		"GrappleSurface",
		"GummiFood",
		"GummiObject",
		"Gun",
		"HandOfGodChaseCameraInfo",
		"HandOfGodCursor",
		"HandOfGodPort",
		"HandOfGodTrigger",
		"HeliumPort",
		"HoGCollectible",
		"HoGDestructibleObject",
		"HoGPuzzleObject",
		"HomerPlayer",
		"InGameVideoPlayer",
		"Item",
		"ItemPlantPoint",
		"LadderSurface",
		"LazyUnlockCheck",
		"LedgeHangSurface",
		"LerpCameraInfo",
		"LetterBoxFx",
		"LisaPlayer",
		"LoadAemsModule",
		"LoadMusicProject",
		"Maggie",
		"MaggieCameraInfo",
		"MaggieDeployPoint",
		"MargePlayer",
		"MarketPlaceOffer",
		"MeshBehavior",
		"MessageBox",
		"MessageRelay",
		"MicrophoneManager",
		"MobInteractDamageableProp",
		"MobInteractDestructible",
		"MobInteractNode",
		"MobInteractTuningRelay",
		"MobItemRandomizer",
		"MobMembershipModifier",
		"ModalScreenEvent",
		"MultiEventChatterBox",
		"MultiManager",
		"MultiRemoveTarget",
		"MusicControlMessage",
		"MusicEvent",
		"MusicMixCategoryChange",
		"Narrator",
		"NodeController",
		"NPCBase",
		"NPCBerserker",
		"NPCDash",
		"NPCDashEatingContestant",
		"NPCEatingContestant",
		"NPCGuardTuningRelay",
		"NPCLardLad",
		"NPCMelee",
		"NPCMeleeFollower",
		"NPCMeleeGuard",
		"NPCMeleeRanged",
		"NPCMeleeRangedFollower",
		"NPCMobileRangedFloater",
		"NPCMobMember",
		"NPCNinja",
		"NPCRanged",
		"NPCRangedGuard",
		"NPCSelmattyLair",
		"NPCSelmattyShire",
		"NPCShakespeare",
		"ObjectDropRandomizer",
		"OfferCheck",
		"OrEventGate",
		"PassiveHeadTrackTarget",
		"PathfinderMusicControl",
		"PingPongPlatform",
		"PlayAudioStream",
		"Player",
		"PlayerBoomMicrophoneOperator",
		"PlayerModeNotify",
		"PlayerMusicMessageHandler",
		"PlayerStart",
		"PlayerTuningOverride",
		"PlayShockProfile",
		"PlaySound",
		"PointCameraInfo",
		"PointSourceMicrophone",
		"PoleSurface",
		"PopCamera",
		"PopulationControlSpawner",
		"Projectile",
		"PushCamera",
		"PushPopCameraPostBlendModifier",
		"RenderTunables",
		"RotatingDoor",
		"RPGSpecialAttack",
		"RPGSystem",
		"ScoreObjective",
		"ScriptableProp",
		"ScriptedSequence",
		"SendScoreEvent",
		"SentientMutator",
		"SetAudioMix",
		"SetDefaultImpactTable",
		"SetDspEffect",
		"SetFollowTarget",
		"SetMusicEventSuffix",
		"ShakeCameraModifierInfo",
		"SimpleChaseCameraInfo",
		"SimpleChatterBox",
		"SimpleObjective",
		"SimpleTeleport",
		"SingleEventChatterBox",
		"SkyboxRender",
		"SlidingDoor",
		"SpaceInvader",
		"SpinPlatform",
		"SplineCameraInfo",
		"StreamInterior",
		"StreamSet",
		"StreamWatcher",
		"Switch",
		"TestEntityDistance",
		"TestEntityExists",
		"TestLastDamage",
		"TestPlayerInput",
		"TestScore",
		"TestVariableContainer",
		"TextMenu",
		"ThoughtBubble",
		"Timer",
		"TouchDetector",
		"TouchDetectorHurt",
		"TrackingCameraInfo",
		"Trampoline",
		"TriggerAuto",
		"TriggerBox",
		"TriggerHurt",
		"TriggerRandom",
		"TrinityGameSequence",
		"TuningOverrideCollectible",
		"TuningOverrideEvent",
		"Turret",
		"UIAnimated",
		"UnlockCheck",
		"Updraft",
		"VariableCollectible",
		"VariableCombiner",
		"VariableCompare",
		"VariableOperator",
		"VariableSwitch",
		"VariableWatcher",
		"WireGrabSurface",
		"ZoneMeshEntity",
		"ZoneRender",
		"ZoneWorld",

		"CAttributeHandler",

		"Zone1",
		"Zone2",
		"Zone3",
		"Zone4",
		"Zone01",
		"Zone02",
		"Zone03",
		"Zone04",

		"Gamehub",

		"CSystemCommands",
		"CEventHandler",
		"SafeObj",
		"AttributeRelay",

		"SetAudioConfig",
		"GlobalAIValueTuner",
		"TriggerFilter",

		"Costume",

		"global",
		"BounceTarget",
		"DebugText",
		"Frame",
		"Animation",
		"StreamScripter",

		"ZoneMesh",

		"StateMachineComponent",
		"ScriptableStateMachineComponent",
		"TunableScriptableSMComponent",
		"RagdollComponent",
		"ChatterComponent",
		"WitnessComponent",
		"StrafeComponent",
		"PressureComponent",
		"CSACrewComponent",
		"DamageComponent",
		"StandardDamageComponent",
		"VehicleDamageComponent",
		"CrewLeaderComponent",
		"PlayerCrewLeaderComponent",
		"UpgradeComponent",
		"PlayerUpgradeComponent",
		"NPCUpgradeComponent",
		"NPCBackUpComponent",
		"NPCCrewComponent",
		"NPCFollowComponent",
		"NPCGuardComponent",
		"NPCPatrolComponent",
		"ObjectDetectionComponent",
		"AudioOcclusionComponent",

		"ZoneStreamEnable",
		"SetMMVariableGUID",
		"SetMMVariableBool",
		"TestUpgrade",
		"StreamBudget",
		"StreamBudgetAssignment",

		"DrawGraphs",
		"RenderingParams",
		"AutoSave",
		"LoadSpawnPoint",
		"TriggerSphere",
		"FleeHintNode",
		"CombatBehavior",
		"AnimateLight",
		"ZoneRenderLOD",
		"BindStreams",
		"SpawnPoint"
	};
}