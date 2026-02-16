using Assets.Scripts;
using System.IO;
using UnityEngine;

namespace AttributeHandlers
{
	public enum DamageLevel : uint
	{
		DamageLevel_REF = 0xFFFFFFFF,
		DAMAGE_LEVEL_UNDEF = 0x0,
		DAMAGE_LEVEL_LIGHT = 0x1,
		DAMAGE_LEVEL_MEDIUM = 0x2,
		DAMAGE_LEVEL_HEAVY = 0x3,
		DAMAGE_LEVEL_STUN = 0x4,
		DAMAGE_LEVEL_KNOCKOUT = 0x5,
		DAMAGE_LEVEL_MAX = 0x6,
		DAMAGE_LEVEL_WINDOW = 0x7,
		DAMAGE_LEVEL_SLAM = 0x8,
		DamageLevel_MAX_VALUE = 0x9,
	}

	public enum DamageType : uint
	{
		DamageType_REF = 0xFFFFFFFF,
		DAMAGE_TYPE_NONE = 0x0,
		DAMAGE_TYPE_HAND_TO_HAND = 0x1,
		DAMAGE_TYPE_GUN = 0x2,
		DAMAGE_TYPE_AUTOMOBILE = 0x3,
		DAMAGE_TYPE_EXPLOSION = 0x4,
		DAMAGE_TYPE_FIRE = 0x5,
		DAMAGE_TYPE_BURN = 0x6,
		DAMAGE_TYPE_OVEN = 0x7,
		DAMAGE_TYPE_FIRELITE = 0x8,
		DAMAGE_TYPE_ELECTROCUTION = 0x9,
		DAMAGE_TYPE_DROWN = 0xA,
		DAMAGE_TYPE_FORCEKILL = 0xB,
		DamageType_MAX_VALUE = 0xC,
	}

	public class EntityDamageDealer : AttributeHandler
	{
		public Guid128 m_entityGUID;
		public string m_damageMsg;
		public float m_fDamageAmount;
		public DamageLevel m_damageLevel;
		public DamageType m_damageType;
		public uint m_flags;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{
					case 0:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_entityGUID = new Guid128(reader);
						break;
					}

					case 1:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_damageMsg = reader.ReadNullTerminatedString();
						break;
					}

					case 2:
					{
						m_fDamageAmount = attr.Data.ToSingleBigEndian();
						break;
					}

					case 3:
					{
						m_damageLevel = (DamageLevel)attr.Data.ToUInt32BigEndian();
						break;
					}

					case 4:
					{
						m_damageType = (DamageType)attr.Data.ToUInt32BigEndian();
						break;
					}

					case 5:
					{
						m_flags = attr.Data.ToUInt32BigEndian();
						break;
					}
				}
			}
		}
	}
}
