using System;
using System.Collections.Generic;
using System.IO;
using Assets.Scripts;
using Assets.Scripts.AttributeHandlers;
using AttributeHandlers;
using UnityEngine;
public class SimGroup
{
	public static Dictionary<uint, Type> AttributeHandlersDict = new()
	{
		{ 0x4B590617, typeof(FuncSpawn) },
		{ 0xB390B11A, typeof(CSystemCommands)},
		{ 0xC8C5D222, typeof(EnterExitTrigger)},
		{ 0xD16A98A9, typeof(TriggerBase)},
		{ 0x7BE194EE, typeof(AndEventGate)},
		{ 0x539B225A, typeof(LoadMusicProject)},
		{ 0xACBDFE47, typeof(TriggerAuto)},
		{ 0xF776AA00, typeof(TestScore)},
		{ 0x087E3D6E, typeof(MultiRemoveTarget)},
		{ 0x62EBE09B, typeof(TriggerRandom)},
		{ 0x29155EC0, typeof(VariableWatcher)},
		{ 0xB1CF0B4B, typeof(EntityDamageDealer)},
		{ 0x5FEF7F11, typeof(TestEntityExists)},
		{ 0xF26BB307 ,typeof(TriggerHurt)},
		{ 0xCC6D6B17, typeof(TestPlayerInput)},
		{ 0x87B7A547, typeof(EventText)},
		//{ 0xB6912FFB, typeof(ChatterAssetSet)},
		{ 0xAE986323, typeof(Animated)},
		{ 0x6DF50074, typeof(MultiManager)},
		{ 0x5EE8CE40, typeof(VariableOperator) },
		{ 0x38523FC3, typeof(Entity)},
		{ 0x862623C0, typeof(DebugText)},
		{ 0x77A210A2, typeof(ZoneRender)},
		{ 0xFFD2E5B1, typeof(Base)},
		{ 0xA018EA5F, typeof(FuncRotate)}
	};

	public class EntityPacket
	{
		public byte nAttrHandlerFlags;
		public byte spawnMask;
		public byte nAttachedRes;
		public byte nAttrPackets;
		public Guid128 GUID;
		public Guid32 BehaviorID;

		public Guid128[] AttachedResources;
		public AttrPacket[] AttributePackets;
	}

	public class AttrPacket
	{
		public Guid32 GUID;
		public ushort nAttrs;
		public uint BitField;
		public List<Attribute> Attributes = new List<Attribute>();
	}

	public class Attribute
	{
		public int Index;
		public byte[] Data;
		public long ReaderPosition;
	}

	public static void LoadSimGroup(byte[] bytes, string strFilePath, GameObject strFileObj)
	{
		var reader = new BinaryReader(new MemoryStream(bytes));

		reader.ReadBytes(4);
		reader.ReadBytes(4);
		var magic = reader.ReadUInt32BigEndian(); // SimG
		if (magic != 1399418183)
		{
			throw new NotImplementedException();
		}

		var version = reader.ReadUInt32BigEndian();
		var guid = new Guid32(reader.ReadUInt32BigEndian());

		var flags = reader.ReadUInt32BigEndian();
		var nEnts = reader.ReadUInt32BigEndian();
		var nEntsDispatched = reader.ReadUInt32BigEndian();
		var sharedDataSize = reader.ReadUInt32BigEndian();
		var dictionarySize = reader.ReadUInt32BigEndian();
		var ppEntPackets = reader.ReadUInt32BigEndian();

		reader.BaseStream.Position = ppEntPackets;
		var pEntPackets = reader.ReadUInt32BigEndian();

		var simgroupParentGo = new GameObject(guid.ToString());
		simgroupParentGo.transform.parent = strFileObj.transform;
		simgroupParentGo.transform.localPosition = Vector3.zero;
		simgroupParentGo.transform.localRotation = Quaternion.identity;
		simgroupParentGo.transform.localScale = Vector3.one;

		reader.BaseStream.Position = pEntPackets;

		for (var i = 0; i < nEnts; i++)
		{
			//Console.WriteLine($"Reading entity packet @ {reader.BaseStream.Position}");

			reader.ReadBytes(16);

			var entPacket = new EntityPacket();
			entPacket.nAttrHandlerFlags = reader.ReadByte();
			entPacket.spawnMask = reader.ReadByte();
			entPacket.nAttachedRes = reader.ReadByte();
			entPacket.nAttrPackets = reader.ReadByte();

			reader.ReadBytes(4);

			var guidOffset = reader.ReadInt32BigEndian();
			var savedPos = reader.BaseStream.Position;
			reader.BaseStream.Position = savedPos - 4 + guidOffset;
			entPacket.GUID = new Guid128(reader.ReadUInt32BigEndian(), reader.ReadUInt32BigEndian(), reader.ReadUInt32BigEndian(), reader.ReadUInt32BigEndian());
			reader.BaseStream.Position = savedPos;
			entPacket.BehaviorID = new Guid32(reader.ReadUInt32BigEndian());

			//verbose = entPacket.BehaviorID.Value == 0xEAC08401;

			//Console.WriteLine($"nAttrHandlerFlags: {entPacket.nAttrHandlerFlags}");
			//Console.WriteLine($"spawnMask: {entPacket.spawnMask}");
			//Console.WriteLine($"nAttachedRes: {entPacket.nAttachedRes}");
			//Console.WriteLine($"nAttrPackets: {entPacket.nAttrPackets}");
			//Console.WriteLine($"GUID: {entPacket.GUID}");
			//if (verbose)
			//{
			//Debug.Log($"Behaviour ID: {entPacket.BehaviorID}");
			//}

			entPacket.AttachedResources = new Guid128[entPacket.nAttachedRes];
			savedPos = reader.BaseStream.Position;
			for (var j = 0; j < entPacket.nAttachedRes; j++)
			{
				reader.BaseStream.Position = savedPos + (j * 4);
				var offset = reader.ReadInt32BigEndian();
				reader.BaseStream.Position = reader.BaseStream.Position - 4 + offset;

				entPacket.AttachedResources[j] = new Guid128(reader.ReadUInt32BigEndian(), reader.ReadUInt32BigEndian(), reader.ReadUInt32BigEndian(), reader.ReadUInt32BigEndian());
			}

			reader.BaseStream.Position = savedPos + (4 * entPacket.nAttachedRes);

			var go = new GameObject(entPacket.BehaviorID.ToString());
			go.transform.parent = simgroupParentGo.transform;

			entPacket.AttributePackets = new AttrPacket[entPacket.nAttrPackets];
			savedPos = reader.BaseStream.Position;
			for (var j = 0; j < entPacket.nAttrPackets; j++)
			{
				reader.BaseStream.Position = savedPos + (j * 4);
				var offset = reader.ReadInt32BigEndian();
				reader.BaseStream.Position = reader.BaseStream.Position - 4 + offset;

				var attrPacket = new AttrPacket();
				//Console.WriteLine($"@ {reader.BaseStream.Position}");
				attrPacket.GUID = new Guid32(reader.ReadUInt32BigEndian());
				attrPacket.nAttrs = reader.ReadUInt16BigEndian();

				if (attrPacket.nAttrs > 16)
				{
					attrPacket.BitField = reader.ReadUInt32();
				}
				else
				{
					attrPacket.BitField = reader.ReadUInt16();
				}

				reader.Align(4);

				for (var k = 0; k < attrPacket.nAttrs; k++)
				{
					var bitSet = attrPacket.BitField.GetBit(k);

					if (!bitSet)
					{
						var pos = reader.BaseStream.Position;
						var read = reader.ReadBytes(4);

						attrPacket.Attributes.Add(new Attribute()
						{
							Index = k,
							Data = read,
							ReaderPosition = pos
						});
					}
				}

				if (AttributeHandlersDict.ContainsKey(attrPacket.GUID.Value))
				{
					var type = AttributeHandlersDict[attrPacket.GUID.Value];

					var comp = (AttributeHandler)go.AddComponent(type);
					comp.STRFile = strFilePath;
					comp.HandleAttributes(reader, attrPacket);

					if (comp is CSystemCommands c && c.m_matrix != null)
					{
						var (position, rotation, scale) = c.m_matrix.GetTRS();

						go.transform.position = position;
						go.transform.rotation = rotation;
						go.transform.localScale = scale;
					}

					if (comp is Base b)
					{
						b.InstanceID = entPacket.GUID;
					}
				}
				else
				{
					var comp = go.AddComponent<DUMMY>();
					comp.Name = attrPacket.GUID.ToString();
					comp.nAttributes = attrPacket.nAttrs;

					comp.HandleAttributes(reader, attrPacket);
				}

				entPacket.AttributePackets[j] = attrPacket;
			}

			go.SetActive(entPacket.spawnMask == 1);

			reader.BaseStream.Position = savedPos + (entPacket.nAttrPackets * 4);
		}
	}
}