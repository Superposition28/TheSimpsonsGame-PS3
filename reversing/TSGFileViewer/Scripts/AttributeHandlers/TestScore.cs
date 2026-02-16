using Assets.Scripts;
using System.IO;
using UnityEngine;

namespace AttributeHandlers
{
	public class TestScore : AttributeHandler
	{
		public uint m_scoreNameHash;
		public float m_operand;
		public uint m_flags;
		public string m_receiveMsg;
		public string m_successMsg;
		public string m_failMsg;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{
					case 0:
					{
						m_scoreNameHash = attr.Data.ToUInt32BigEndian();
						break;
					}

					case 1:
					{
						m_operand = attr.Data.ToSingleBigEndian();
						break;
					}

					case 2:
					{
						m_flags = attr.Data.ToUInt32BigEndian();
						break;
					}

					case 3:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_receiveMsg = reader.ReadNullTerminatedString();
							break;
					}

					case 4:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_successMsg = reader.ReadNullTerminatedString();
							break;
					}

					case 5:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_failMsg = reader.ReadNullTerminatedString();
							break;
					}
				}
			}
		}
	}
}
