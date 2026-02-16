using System.IO;
using Assets.Scripts;
using UnityEngine;

namespace AttributeHandlers
{
	public class TestPlayerInput : AttributeHandler
	{
		public string m_inputTargetName;
		public string m_outputTargetName;
		public uint m_PlayerInputPattern01;
		public float m_waitTime;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{
					case 0:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_inputTargetName = reader.ReadNullTerminatedString();
						break;
					}

					case 1:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_outputTargetName = reader.ReadNullTerminatedString();
						break;
					}

					case 2:
					{
						m_PlayerInputPattern01 = attr.Data.ToUInt32BigEndian();
						break;
					}

					case 3:
					{
						m_waitTime = attr.Data.ToSingleBigEndian();
						break;
					}
				}
			}
		}
	}
}