using Assets.Scripts;
using System.IO;
using UnityEngine;

namespace AttributeHandlers
{
	public class VariableWatcher : AttributeHandler
	{
		public string m_targetName;
		public string m_deactivate;
		public string m_target;
		public float m_fDelay;
		public uint m_variableId;
		public uint m_uiCondition;
		public int m_iThreshold;
		public uint m_options;
		public int m_conditionMetThreshold;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{
					case 0:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_targetName = reader.ReadNullTerminatedString();
						break;
					}

					case 1:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_deactivate = reader.ReadNullTerminatedString();
						break;
					}

					case 2:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian(); // negative offset
						m_target = reader.ReadNullTerminatedString();
						break;
					}

					case 3:
					{
						m_fDelay = attr.Data.ToSingleBigEndian();
						break;
					}

					case 4:
					{
						m_variableId = attr.Data.ToUInt32BigEndian();
						break;
					}

					case 5:
					{
						m_uiCondition = attr.Data.ToUInt32BigEndian();
						break;
					}

					case 6:
					{
						m_iThreshold = attr.Data.ToInt32BigEndian();
						break;
					}

					case 7:
					{
						m_options = attr.Data.ToUInt32BigEndian();
						break;
					}

					case 8:
					{
						m_conditionMetThreshold = attr.Data.ToInt32BigEndian();
						break;
					}
				}
			}
		}
	}
}