using Assets.Scripts;
using System.IO;
using UnityEngine;

namespace AttributeHandlers
{
	public class TriggerHurt : AttributeHandler
	{
		public float m_damageAmount;
		public DamageType m_damageType;
		public DamageLevel m_damageLevel;
		public uint m_triggerHurtFlags;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{
					case 0:
					{
						m_damageAmount = attr.Data.ToSingleBigEndian();
						break;
					}

					case 1:
					{
						m_damageType = (DamageType)attr.Data.ToUInt32BigEndian();
						break;
					}

					case 2:
					{
						m_damageLevel = (DamageLevel)attr.Data.ToUInt32BigEndian();
						break;
					}

					case 3:
					{
						m_triggerHurtFlags = attr.Data.ToUInt32BigEndian();
						break;
					}
				}
			}
		}
	}
}
